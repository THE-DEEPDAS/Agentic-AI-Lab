"""Experiment runner: tasks x conditions x runs, with full traces, resume and error handling."""
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from collections import Counter

from . import __version__
from .common import ROOT, condition_map, jdump, load_pool, load_tasks, path, read_text
from .context import build_context, make_filler, schema_chars
from .models import RateLimiter, call_with_retries, make_provider
from .scoring import score_call


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _file_sha(rel):
    with open(path(rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _git_head():
    try:
        r = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _pkg_version(name):
    try:
        import importlib.metadata as md
        return md.version(name)
    except Exception:  # noqa: BLE001
        return None


def default_out_dir(cfg):
    m = cfg["model"]
    if m["provider"].startswith("mock"):
        return path("results", "mock_smoke")
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in str(m["name"]))
    return path("results", f"{m['provider']}_{safe}_{dt.datetime.now(dt.timezone.utc):%Y%m%d}")


class Runner:
    def __init__(self, cfg, out_dir, condition_ids, runs=None, limit=None, workers=None, rps=None):
        self.cfg = cfg
        self.out_dir = out_dir
        self.cmap = condition_map(cfg)
        missing = [c for c in condition_ids if c not in self.cmap]
        if missing:
            raise SystemExit(f"unknown conditions: {missing}")
        self.condition_ids = condition_ids
        self.n_runs = runs or cfg["experiment"]["n_runs"]
        self.tasks = load_tasks(cfg)
        if limit:
            self.tasks = self.tasks[:limit]
        self.pool = load_pool(cfg)
        self.system_prompt = read_text(cfg["prompts"]["system"]).strip()
        self.user_tpl = read_text(cfg["prompts"]["user"]).rstrip("\n")
        self.filler_corpus = read_text(cfg["prompts"]["filler"])
        self.provider = make_provider(cfg["model"])
        self.is_mock = cfg["model"]["provider"].startswith("mock")
        self.limiter = RateLimiter(rps if rps is not None else cfg["runtime"]["max_requests_per_second"])
        self.workers = workers or cfg["runtime"]["workers"]
        self.lock = threading.Lock()
        self.models_seen = Counter()
        self.ctx_cache = {}
        self.done_keys = set()
        self.trace_files = {}

    # ---------- contexts ----------
    def context(self, task, cid):
        key = (task["uuid"], cid)
        if key not in self.ctx_cache:
            cond = self.cmap[cid]
            self.ctx_cache[key] = build_context(task, cond, self.pool, self.cfg["experiment"]["design_seed"])
        return self.ctx_cache[key]

    def system_for(self, task, cid):
        cond = self.cmap[cid]
        if "padded_to" not in cond:
            return self.system_prompt
        big = self.context(task, cond["padded_to"])
        small = self.context(task, cid)
        extra = schema_chars(big["tools"]) - schema_chars(small["tools"])
        filler = make_filler(extra, self.filler_corpus)
        return self.system_prompt + "\n\nBackground notes (not relevant to the task):\n" + filler

    # ---------- IO ----------
    def _trace_path(self, cid, run):
        return os.path.join(self.out_dir, "traces", cid, f"run{run}.jsonl")

    def _load_done(self):
        for cid in self.condition_ids:
            for run in range(1, self.n_runs + 1):
                p = self._trace_path(cid, run)
                if os.path.exists(p):
                    with open(p, encoding="utf-8") as f:
                        for line in f:
                            try:
                                self.done_keys.add((cid, run, json.loads(line)["uuid"]))
                            except Exception:  # noqa: BLE001 - truncated last line after a crash
                                pass

    def _write_contexts(self):
        d = os.path.join(self.out_dir, "contexts")
        os.makedirs(d, exist_ok=True)
        for cid in self.condition_ids:
            p = os.path.join(d, f"{cid}.jsonl.gz")
            if os.path.exists(p):
                continue
            with gzip.open(p, "wt", encoding="utf-8") as f:
                for t in self.tasks:
                    c = self.context(t, cid)
                    f.write(json.dumps({"uuid": t["uuid"], "tools": c["tools"], "gold": c["gold"],
                                        "gold_position": c["gold_position"]}, ensure_ascii=False) + "\n")

    def _append(self, cid, run, rec):
        p = self._trace_path(cid, run)
        with self.lock:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------- one job ----------
    def _sample(self, task, cid, run, task_idx, j, ctx, system, user):
        mcfg = self.cfg["model"]
        seed = None
        if getattr(self.provider, "supports_seed", False):
            seed = self.cfg["experiment"]["base_run_seed"] + run * 100000 + task_idx + j * 7919
        meta = None
        if self.provider.name == "mock_oracle":
            meta = {"gold_name": task["label"]["name"], "gold_args": task["label"]["input"]}
        r = call_with_retries(
            self.provider, self.limiter, mcfg,
            system=system, user=user, tools=ctx["tools"], temperature=mcfg["temperature"],
            top_p=mcfg["top_p"], seed=seed, max_tokens=mcfg["max_tokens"], meta=meta)
        r["seed"] = seed
        return r

    def _job(self, run, task_idx, cid):
        task = self.tasks[task_idx]
        if (cid, run, task["uuid"]) in self.done_keys:
            return None
        cond = self.cmap[cid]
        ctx = self.context(task, cid)
        system = self.system_for(task, cid)
        user = self.user_tpl.format(query=task["query"])
        k = cond.get("self_consistency_k", 1)
        t0 = time.perf_counter()
        samples = [self._sample(task, cid, run, task_idx, j, ctx, system, user) for j in range(k)]
        wall = time.perf_counter() - t0

        # self-consistency: majority vote on the called tool name, first sample with that name wins
        scored = [score_call(task, ctx, s, self.cfg["scoring"]) for s in samples]
        if k > 1:
            votes = Counter(sc["pred_name"] for sc in scored if sc["pred_name"])
            winner = votes.most_common(1)[0][0] if votes else None
            idx = next((i for i, sc in enumerate(scored) if sc["pred_name"] == winner), 0)
        else:
            idx = 0
        final = scored[idx]
        usage_in = sum(s["usage"]["input_tokens"] for s in samples)
        usage_out = sum(s["usage"]["output_tokens"] for s in samples)
        for s in samples:
            if s.get("model_returned"):
                self.models_seen[s["model_returned"]] += 1
        rec = {
            "uuid": task["uuid"], "task_idx": task_idx, "domain": task["domain"], "condition": cid,
            "run": run, "ts": _now(),
            "n_tools": ctx["n_actual"], "gold_position": ctx["gold_position"],
            "context_sha": _sha(jdump([t["name"] for t in ctx["tools"]])),
            "tool_names": [t["name"] for t in ctx["tools"]],
            "system": system if "padded_to" not in cond else system[:400] + f"...[filler, {len(system)} chars total]",
            "user": user,
            "samples": [{"seed": s["seed"], "text": s["text"], "tool_calls": s["tool_calls"],
                         "error": s["error"], "usage": s["usage"], "latency_s": round(s["latency_s"], 4),
                         "attempts": s["attempts"], "model_returned": s["model_returned"]} for s in samples],
            "chosen_sample": idx,
            "model_calls": k, "input_tokens": usage_in, "output_tokens": usage_out,
            "tokens_estimated": any(s["usage"].get("estimated") for s in samples),
            "latency_s": round(wall, 4),
            "label": {"name": task["label"]["name"], "input": task["label"]["input"],
                      "similar": [s["name"] for s in task["label"].get("similar_tools", [])]},
            "score": final,
            "mock": self.is_mock,
        }
        self._append(cid, run, rec)
        return rec

    # ---------- driver ----------
    def estimate(self):
        """Offline token estimate (chars/4) for the planned jobs; no model calls."""
        per_cond = {}
        for cid in self.condition_ids:
            cond = self.cmap[cid]
            k = cond.get("self_consistency_k", 1)
            toks = []
            for t in self.tasks:
                sysmsg = self.system_for(t, cid)
                ctx = self.context(t, cid)
                toks.append((len(sysmsg) + len(t["query"]) + schema_chars(ctx["tools"])) / 4 * k)
            per_cond[cid] = {"mean_input_tokens_per_task": sum(toks) / len(toks),
                             "total_input_tokens": sum(toks) * self.n_runs,
                             "calls": len(toks) * self.n_runs * k}
        return per_cond

    def write_manifest(self, started, finished=None):
        cfg = self.cfg
        m = cfg["model"]
        manifest = {
            "rp2_version": __version__,
            "mock_run": self.is_mock,
            "NOT_A_RESULT": self.is_mock,
            "started_utc": started, "finished_utc": finished,
            "python": sys.version.split()[0], "platform": platform.platform(),
            "packages": {p: _pkg_version(p) for p in ("anthropic", "openai", "jsonschema", "numpy", "PyYAML")},
            "repo_git_head": _git_head(),
            "model_requested": m["name"], "provider": m["provider"], "base_url": m.get("base_url"),
            "model_strings_returned_by_api": dict(self.models_seen),
            "decoding": {"temperature": m["temperature"],
                         "top_p": m["top_p"] if getattr(self.provider, "sends_top_p", False) else "not sent (provider adapter)",
                         "max_tokens": m["max_tokens"],
                         "seed": ("base_run_seed + run*100000 + task_idx (+7919*j for self-consistency)"
                                  if getattr(self.provider, "supports_seed", False) else "not supported by provider")},
            "n_runs": self.n_runs, "n_tasks": len(self.tasks), "conditions": self.condition_ids,
            "prompt_sha256": {k: _file_sha(v) for k, v in cfg["prompts"].items()},
            "data_sha256": {"subset": _file_sha(cfg["experiment"]["subset_file"]),
                            "tool_pool": _file_sha(cfg["experiment"]["tool_pool_file"])},
            "config": cfg,
        }
        with open(os.path.join(self.out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def run(self, max_jobs=None, progress_every=50):
        os.makedirs(self.out_dir, exist_ok=True)
        self._load_done()
        self._write_contexts()
        started = _now()
        jobs = [(run, i, cid) for run in range(1, self.n_runs + 1)
                for i in range(len(self.tasks)) for cid in self.condition_ids
                if (cid, run, self.tasks[i]["uuid"]) not in self.done_keys]
        if max_jobs:
            jobs = jobs[:max_jobs]
        total, done, fails = len(jobs), 0, 0
        print(f"[runner] {total} jobs to run ({len(self.done_keys)} already done) -> {self.out_dir}", flush=True)
        self.write_manifest(started)
        with cf.ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = [ex.submit(self._job, *j) for j in jobs]
            for fu in cf.as_completed(futs):
                try:
                    rec = fu.result()
                except Exception as e:  # noqa: BLE001 - a bug in one job must not kill the run
                    fails += 1
                    print(f"[runner] job crashed: {type(e).__name__}: {e}", flush=True)
                    continue
                done += 1
                if rec and rec["score"]["failure"] == "api_error":
                    fails += 1
                if done % progress_every == 0 or done == total:
                    print(f"[runner] {done}/{total} done, {fails} failed jobs", flush=True)
        self.write_manifest(started, _now())
        return {"jobs": total, "completed": done, "failed": fails}
