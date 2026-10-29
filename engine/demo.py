# Job-search agent engine
# File:    engine/demo.py
# Purpose: Builds a fictional agent home and runs every step on it.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""Builds a fully fictional demo agent home and runs every step on it.

    ./run.sh demo

Result: docs/demo/home/ (ignored by git) and refreshed previews in
docs/demo/preview/. No real person, employer posting or URL is involved.
"""
import os
import shutil

from .home import DEMO_DIR, Home
from . import cli

DATA = os.path.join(DEMO_DIR, "data")


def _run(home, *argv):
    print(f"\n$ ./run.sh {' '.join(argv)}")
    cli.main(["--home", home.root, *argv])


def build(_home_arg=None):
    root = os.path.join(DEMO_DIR, "home")
    if os.path.exists(root):
        try:
            shutil.rmtree(root)
        except OSError:
            from datetime import datetime
            root = root + "_" + datetime.now().strftime("%Y%m%d%H%M%S")
    h = Home(root)
    _run(h, "init")
    shutil.copy2(os.path.join(DATA, "search_config.json"), h.path("search_config"))
    shutil.copy2(os.path.join(DATA, "employers.json"), h.path("employers"))

    print("\n--- 1. Minimum service: search config only, no candidate data ---")
    _run(h, "status")
    _run(h, "add-postings", os.path.join(DATA, "postings_week1.json"))
    shutil.copy2(os.path.join(DATA, "decisions_sync.json"), h.path("decisions"))
    _run(h, "sync")
    _run(h, "add-postings", os.path.join(DATA, "postings_week2.json"))
    _run(h, "weekly", "Demo run with fictional postings.")

    print("\n--- 2. Accepted posting, no candidate data: template documents ---")
    _run(h, "tailor", "pending")
    _run(h, "tailor", "template", "--all-pending")

    print("\n--- 3. Candidate data added later: form, then a CV-derived fragment ---")
    _run(h, "intake", "form", os.path.join(DATA, "fictional_candidate_form.json"))
    _run(h, "intake", "fragment", os.path.join(DATA, "fictional_cv_fragment.json"))
    _run(h, "intake", "conflicts")
    _run(h, "status")

    print("\n--- 4. Full tailoring: render a spec written from the profile ---")
    key = "https://example.com/nordlys/jobs/view/1001/||FPGA Engineer"
    _run(h, "tailor", "check", os.path.join(DATA, "example_cv_spec.json"))
    _run(h, "tailor", "render", os.path.join(DATA, "example_cv_spec.json"), "--posting", key)
    _run(h, "tailor", "jd", key)
    _run(h, "tailor", "done", key)

    prev = os.path.join(DEMO_DIR, "preview")
    os.makedirs(prev, exist_ok=True)
    shutil.copy2(h.path("weekly_html"), os.path.join(prev, "jobs-on-market.html"))
    summaries = sorted(os.listdir(h.path("weekly_summary")))
    if summaries:
        shutil.copy2(os.path.join(h.path("weekly_summary"), summaries[-1]), os.path.join(prev, "weekly_summary_example.md"))
    for d in ("cv_out", "cl_out"):
        for f in os.listdir(h.path(d)):
            if f.endswith((".docx", ".md")):
                shutil.copy2(os.path.join(h.path(d), f), os.path.join(prev, f))
    print(f"\ndemo home: {root}\npreviews: {prev}")
