"""Model providers behind one interface, plus retry/pacing and an offline mock.

Every provider implements
    chat(system, user, tools, temperature, top_p, seed, max_tokens, meta) -> dict
returning
    {"error": None|str, "text": str, "tool_calls": [{"name", "arguments"}],
     "usage": {"input_tokens", "output_tokens", "estimated": bool},
     "model_returned": str|None}
Wall-clock latency is measured by the caller around the whole attempt sequence.

The mock providers exist ONLY to test the pipeline offline. Their outputs are not results and
the runner stamps every mock run as such in its manifest and file names.
"""
import json
import os
import random
import re
import threading
import time


class RateLimiter:
    def __init__(self, rps):
        self.min_gap = 1.0 / rps if rps and rps > 0 else 0.0
        self.lock = threading.Lock()
        self.next_t = 0.0

    def wait(self):
        if not self.min_gap:
            return
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next_t)
            self.next_t = t + self.min_gap
        if t > now:
            time.sleep(t - now)


def _estimate_tokens(*parts):
    return int(sum(len(p) for p in parts) / 4)


class AnthropicProvider:
    name = "anthropic"
    supports_seed = False
    sends_top_p = False

    def __init__(self, mcfg):
        import anthropic  # imported lazily so mock runs need no SDK

        key = os.environ.get(mcfg["api_key_env"])
        if not key:
            raise SystemExit(f"environment variable {mcfg['api_key_env']} is not set")
        self.client = anthropic.Anthropic(api_key=key, timeout=mcfg["timeout_s"], max_retries=0)
        self.model = mcfg["name"]

    def chat(self, system, user, tools, temperature, top_p, seed, max_tokens, meta=None):
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[{"name": t["name"], "description": t["description"],
                    "input_schema": t.get("input_schema") or {"type": "object", "properties": {}}}
                   for t in tools],
            tool_choice={"type": "auto"},
        )
        calls = [{"name": b.name, "arguments": b.input} for b in resp.content if b.type == "tool_use"]
        text = "".join(b.text for b in resp.content if b.type == "text")
        return {"error": None, "text": text, "tool_calls": calls,
                "usage": {"input_tokens": resp.usage.input_tokens,
                          "output_tokens": resp.usage.output_tokens, "estimated": False},
                "model_returned": resp.model}


class OpenAICompatProvider:
    name = "openai_compat"
    supports_seed = True
    sends_top_p = True

    def __init__(self, mcfg):
        from openai import OpenAI

        key = os.environ.get(mcfg["api_key_env"], "EMPTY" if mcfg.get("base_url") else None)
        if not key:
            raise SystemExit(f"environment variable {mcfg['api_key_env']} is not set")
        self.client = OpenAI(api_key=key, base_url=mcfg.get("base_url"),
                             timeout=mcfg["timeout_s"], max_retries=0)
        self.model = mcfg["name"]
        self.reasoning_effort = mcfg.get("reasoning_effort")
        # Gemini's OpenAI-compatible endpoint rejects the OpenAI-only `seed`
        # field. Other compatible providers may support it.
        self.supports_seed = "generativelanguage.googleapis.com" not in (mcfg.get("base_url") or "")

    def chat(self, system, user, tools, temperature, top_p, seed, max_tokens, meta=None):
        request = dict(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            tools=[{"type": "function",
                    "function": {"name": t["name"], "description": t["description"],
                                 "parameters": t.get("input_schema") or {"type": "object", "properties": {}}}}
                   for t in tools],
            tool_choice="auto",
            temperature=temperature, top_p=top_p, max_tokens=max_tokens,
        )
        if self.supports_seed:
            request["seed"] = seed
        # NVIDIA DeepSeek V4.1 Flash supports numeric reasoning_effort (1-100).
        # Keep it low for this tool-selection benchmark; otherwise the hosted
        # free endpoint may spend excessive time in hidden reasoning.
        if self.reasoning_effort is not None:
            request["extra_body"] = {"reasoning_effort": self.reasoning_effort}
        resp = self.client.chat.completions.create(**request)
        msg = resp.choices[0].message
        calls = [{"name": c.function.name, "arguments": c.function.arguments}
                 for c in (msg.tool_calls or [])]
        u = resp.usage
        return {"error": None, "text": msg.content or "", "tool_calls": calls,
                "usage": {"input_tokens": getattr(u, "prompt_tokens", 0) or 0,
                          "output_tokens": getattr(u, "completion_tokens", 0) or 0, "estimated": False},
                "model_returned": resp.model}


_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("the a an of in on for to and or is are what how with from by at as it this that me my i you "
            "can please find get give show tell about".split())


def _words(s):
    return [w for w in _WORD.findall(s.casefold()) if w not in _STOP]


class MockProvider:
    """Keyword-overlap 'model' with seeded noise. Never sees the label. For pipeline tests only."""
    name = "mock"
    supports_seed = True
    sends_top_p = True

    def __init__(self, mcfg=None):
        self.model = "mock-keyword-v1"

    def chat(self, system, user, tools, temperature, top_p, seed, max_tokens, meta=None):
        rng = random.Random(f"{seed}:{user}:{len(tools)}")
        q = set(_words(user))
        best, best_s = None, -1e9
        for t in tools:
            d = _words(t["name"].replace("_", " ").replace("-", " ") + " " + t["description"])
            s = len(q & set(d)) / (len(set(d)) ** 0.5 + 1e-9) + rng.gauss(0, 0.15 * temperature + 0.02)
            if s > best_s:
                best, best_s = t, s
        schema = best.get("input_schema") or {}
        args = {}
        nums = re.findall(r"-?\d+\.\d+|-?\d+", user)
        for k, p in (schema.get("properties") or {}).items():
            req = k in (schema.get("required") or [])
            typ = p.get("type")
            if re.search(r"lat", k, re.I) and nums:
                args[k] = nums[0]
            elif re.search(r"lon|lng", k, re.I) and len(nums) > 1:
                args[k] = nums[1]
            elif typ == "string" and "enum" not in p and (req or k in ("query", "address", "keywords", "url")):
                args[k] = user.strip()
            elif typ == "array" and req:
                args[k] = [user.strip()]
        text = ""
        usage_in = _estimate_tokens(system, user, json.dumps(tools, ensure_ascii=False))
        return {"error": None, "text": text, "tool_calls": [{"name": best["name"], "arguments": args}],
                "usage": {"input_tokens": usage_in, "output_tokens": _estimate_tokens(json.dumps(args)) + 8,
                          "estimated": True},
                "model_returned": self.model}


class MockOracleProvider(MockProvider):
    """Returns the gold call (test-only: proves the scorer gives 100% to a perfect model)."""
    name = "mock_oracle"

    def chat(self, system, user, tools, temperature, top_p, seed, max_tokens, meta=None):
        r = super().chat(system, user, tools, temperature, top_p, seed, max_tokens, meta)
        r["tool_calls"] = [{"name": meta["gold_name"], "arguments": dict(meta["gold_args"])}]
        return r


class MockFlakyProvider(MockProvider):
    """Raises on a fraction of calls so retry/error handling can be tested."""
    name = "mock_flaky"

    def chat(self, system, user, tools, temperature, top_p, seed, max_tokens, meta=None):
        if random.Random(f"flaky:{seed}:{user}").random() < 0.15:
            raise RuntimeError("simulated provider failure")
        return super().chat(system, user, tools, temperature, top_p, seed, max_tokens, meta)


def make_provider(mcfg):
    p = mcfg["provider"]
    if p in ("mock", "mock_oracle", "mock_flaky"):
        return {"mock": MockProvider, "mock_oracle": MockOracleProvider, "mock_flaky": MockFlakyProvider}[p](mcfg)
    if not mcfg.get("name"):
        raise SystemExit("config model.name is null: set the exact model version string before a real run")
    if p == "anthropic":
        return AnthropicProvider(mcfg)
    if p == "openai_compat":
        return OpenAICompatProvider(mcfg)
    raise SystemExit(f"unknown provider {p}")


def call_with_retries(provider, limiter, mcfg, **kw):
    """Run chat() with pacing and exponential backoff. Never raises: returns error in the dict."""
    t0 = time.perf_counter()
    last = None
    attempts = 0
    for attempt in range(mcfg.get("max_retries", 5) + 1):
        attempts = attempt + 1
        limiter.wait()
        try:
            r = provider.chat(**kw)
            r["latency_s"] = time.perf_counter() - t0
            r["attempts"] = attempts
            return r
        except Exception as e:  # noqa: BLE001 - provider SDKs raise many types
            last = f"{type(e).__name__}: {e}"
            time.sleep(min(30.0, (2 ** attempt) * 0.5) if provider.name != "mock_flaky" else 0.0)
    return {"error": last, "text": "", "tool_calls": [],
            "usage": {"input_tokens": 0, "output_tokens": 0, "estimated": False},
            "model_returned": None, "latency_s": time.perf_counter() - t0, "attempts": attempts}
