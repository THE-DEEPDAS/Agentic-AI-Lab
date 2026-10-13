"""Shared helpers: config, data loading, prompt files."""
import json
import os
import yaml
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def path(*parts):
    return os.path.join(ROOT, *parts)


def load_config(config_path=None):
    # Load the project-local .env without overwriting variables already set in
    # the shell. Keys stay out of config.yaml and source control.
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
    with open(config_path or path("configs", "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_tasks(cfg):
    with open(path(cfg["experiment"]["subset_file"]), encoding="utf-8") as f:
        return json.load(f)["tasks"]


def load_pool(cfg):
    with open(path(cfg["experiment"]["tool_pool_file"]), encoding="utf-8") as f:
        return json.load(f)["tools"]


def read_text(rel):
    with open(path(rel), encoding="utf-8") as f:
        return f.read()


def condition_map(cfg):
    return {c["id"]: c for c in cfg["conditions"]}


def jdump(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
