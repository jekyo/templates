#!/usr/bin/env python3
"""Validate a jekyo template: resolve inputs with dummy values, strip the
inputs block, and run `jekyo render` on the result. Exit 0 = valid.

Usage: validate.py <template-dir> [path-to-jekyo-binary]
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

def main():
    tdir = Path(sys.argv[1])
    jekyo = sys.argv[2] if len(sys.argv) > 2 else "jekyo"
    src = (tdir / "jekyo.yaml").read_text()

    # Parse the inputs block (names + kind/default) without a YAML lib.
    inputs = {}
    m = re.search(r"^inputs:\n((?:[ \t].*\n|\n)*)", src, re.M)
    if m:
        block = m.group(1)
        for im in re.finditer(r"^  ([A-Z][A-Z0-9_]*):\n((?:^    .*\n)*)", block, re.M):
            name, body = im.group(1), im.group(2)
            kind = re.search(r"^\s*kind:\s*(\S+)", body, re.M)
            default = re.search(r"^\s*default:\s*(.+)$", body, re.M)
            inputs[name] = {
                "kind": kind.group(1) if kind else "string",
                "default": default.group(1).strip().strip("\"'") if default else "",
            }

    env = {}
    out = src
    for name, spec in inputs.items():
        if spec["kind"] == "secret":
            env[name] = "dummy-secret-0123456789"
            continue  # secrets stay as ${NAME}, provided via --env-file
        val = spec["default"]
        if not val:
            val = {
                "domain": "valid.example.com",
                "size": "1Gi",
            }.get(spec["kind"], "dummy-value")
        out = out.replace("${" + name + "}", val)

    out = re.sub(r"^inputs:\n(?:[ \t].*\n|\n)*", "", out, count=1, flags=re.M)

    with tempfile.TemporaryDirectory() as tmp:
        yml = Path(tmp) / "jekyo.yaml"
        yml.write_text(out)
        envfile = Path(tmp) / ".env"
        envfile.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
        r = subprocess.run(
            [jekyo, "render", "-f", str(yml), "--env-file", str(envfile)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(r.stderr.strip() or r.stdout.strip())
            sys.exit(1)
    print("OK")

if __name__ == "__main__":
    main()
