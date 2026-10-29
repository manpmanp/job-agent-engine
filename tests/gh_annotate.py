#!/usr/bin/env python3
# Job-search agent engine
# File:    tests/gh_annotate.py
# Purpose: Turns the end of a log file into a GitHub Actions annotation, so a failure on another system can be read through the API.
# Author:  manpmanp <manp.node@gmail.com>. Generated with Claude (Anthropic), under the author's direction and review. MIT.
"""    python tests/gh_annotate.py <level: error|notice> <title> <file> [max chars]"""
import sys

level, title, path = sys.argv[1:4]
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 3800
try:
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
except OSError as e:
    text = f"(no log: {e})"
text = text[-limit:]
esc = text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
print(f"::{level} title={title}::{esc}")
