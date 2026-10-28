#!/usr/bin/env python3
"""Load only reviewed app manifests; workflow inputs never become shell commands."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]


def load_app(name):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", name):
        raise ValueError("Invalid app name")
    config = json.loads((ROOT / "apps" / f"{name}.json").read_text())
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["repository"]):
        raise ValueError("Invalid repository")
    path = PurePosixPath(config["directory"])
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Directory must be relative and stay inside checkout")
    if config["adapter"] != "expo":
        raise ValueError("Only the expo adapter is implemented so far")
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", config["bundle_id"]):
        raise ValueError("Invalid bundle ID")
    if not re.fullmatch(r"[A-Za-z0-9_. -]+", config["scheme"]):
        raise ValueError("Invalid Xcode scheme")
    for suffix in config["extension_suffixes"]:
        if not re.fullmatch(r"[A-Za-z0-9-]+", suffix):
            raise ValueError("Invalid extension suffix")
    config["app"] = name
    config["bundle_ids"] = [config["bundle_id"]] + [
        f'{config["bundle_id"]}.{suffix}' for suffix in config["extension_suffixes"]
    ]
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app")
    parser.add_argument("--ref", default="")
    args = parser.parse_args()
    config = load_app(args.app)
    ref = args.ref or config["default_ref"]
    if not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", ref) or ref.startswith("-") or ".." in ref:
        raise ValueError("Invalid source ref")
    config["ref"] = ref
    serialized = json.dumps(config, separators=(",", ":"))
    print(json.dumps(config, indent=2))
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(f"config={serialized}\n")


if __name__ == "__main__":
    main()
