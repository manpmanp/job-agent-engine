# Job-search agent engine
# File:    engine/reset.py
# Purpose: Start over: moves chosen parts of an agent home into a dated backup folder and recreates them blank.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.4
# Date:    2026-10-29

"""
Nothing is deleted. Each chosen part is moved, with its place in the folder
kept, into <home>/backups/<date_time>/, then the agent home is completed
again from the blank templates (as on first start). To undo, move the
files back from the backup folder.

Parts:
    settings   search setup, employers, job sites, document look, writing
               style, checks; also switches the daily run off
    keys       API keys and the online-search connection (inputs/secrets.json)
    profile    your profile, uploaded CVs and letters, reference files,
               personal rules and characteristics
    postings   tracker, decisions, notes, logs, per-posting choices
    documents  generated CVs, cover letters and snapshots
"""
import os
import shutil
from datetime import datetime

PARTS = {
    "settings": ("search_config", "employers", "document_style", "document_conventions", "tailoring_checks"),
    "keys": (),
    "profile": ("candidate", "references", "characteristics", "tailoring_rules", "intake_dir"),
    "postings": ("state_dir",),
    "documents": ("output_dir",),
}
LABELS = {
    "settings": "Settings: what to search for, employers, job sites, document look and writing style (also turns the daily run off)",
    "keys": "API keys and the online-search connection",
    "profile": "Your profile, uploaded CVs and letters, reference files and personal rules",
    "postings": "Postings, decisions, notes and logs",
    "documents": "Generated CVs, cover letters and job-description snapshots",
}


def _paths(home, part):
    out = []
    for key in PARTS[part]:
        if key == "intake_dir":
            out.append(os.path.dirname(home.path("intake_cv")))
        elif key == "state_dir":
            out.append(os.path.dirname(home.path("notes")))
        elif key == "output_dir":
            out.append(os.path.dirname(home.path("weekly_html")))
        else:
            out.append(home.path(key))
    if part == "keys":
        out.append(os.path.join(home.path("inputs"), "secrets.json"))
    return out


def reset(home, parts):
    """Moves the chosen parts into a backup folder and recreates them blank.
    Returns {"backup": folder or None, "moved": [relative paths], "parts": [...]}."""
    parts = [p for p in parts if p in PARTS]
    if not parts:
        raise ValueError("choose at least one part to reset")
    root = os.path.realpath(home.root)
    backup = os.path.join(root, "backups", datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    moved = []
    if "settings" in parts:
        try:
            from . import schedule
            schedule.remove(home)
        except Exception:
            pass
    for part in parts:
        for p in _paths(home, part):
            full = os.path.realpath(p)
            if not os.path.exists(full) or not full.startswith(root + os.sep):
                continue
            rel = os.path.relpath(full, root)
            dest = os.path.join(backup, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(full, dest)
            moved.append(rel)
    from .cli import ensure_home, ensure_state
    ensure_home(home)
    ensure_state(home)
    return {"backup": backup if moved else None, "moved": moved, "parts": parts}
