#!/usr/bin/env python3
# Job-search agent engine
# File:    tests/platform_compare.py
# Purpose: Compares the platform_check.py results of macOS, Windows and Linux side by side; fails when the app behaves differently.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.5
# Date:    2026-10-29

"""    python tests/platform_compare.py results/*.json"""
import json
import sys

SYSTEM_SPECIFIC = {"system", "mode"}


def flat(d, prefix=""):
    out = {}
    for k, v in (d.items() if isinstance(d, dict) else []):
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flat(v, key + "."))
        else:
            out[key] = json.dumps(v, ensure_ascii=False, sort_keys=True)
    return out


def main(paths):
    runs = {}
    for p in paths:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        runs[f"{d['system']}/{d['mode']}"] = flat({k: v for k, v in d.items() if k not in SYSTEM_SPECIFIC})
    names = sorted(runs)
    keys = sorted(set().union(*runs.values()))
    diffs = [k for k in keys if len({runs[n].get(k) for n in names}) > 1]
    width = max(len(k) for k in keys)
    print("checked:", ", ".join(names))
    print(f"{'item'.ljust(width)}  " + "  ".join(n.ljust(16) for n in names))
    for k in keys:
        vals = [runs[n].get(k, "(missing)") for n in names]
        mark = "DIFF " if k in diffs else "same "
        shown = [v if len(v) <= 16 else v[:13] + "..." for v in vals]
        print(f"{mark}{k.ljust(width)}  " + "  ".join(s.ljust(16) for s in shown))
    if diffs:
        print(f"\n{len(diffs)} difference(s):")
        for k in diffs:
            for n in names:
                print(f"  {k} [{n}]: {runs[n].get(k, '(missing)')}")
        sys.exit(1)
    print(f"\nall {len(keys)} items are the same on every system")


if __name__ == "__main__":
    main(sys.argv[1:])
