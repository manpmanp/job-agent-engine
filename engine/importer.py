# Job-search agent engine
# File:    engine/importer.py
# Purpose: Brings an earlier agent's folder into this agent home: tracker, rejection log, notes, employers and documents, without duplicates.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.10
# Date:    2026-11-05

"""
    ./run.sh --home ~/JobAgent import <old folder> [--dry-run]

The old folder can be another agent home made by this engine, or an agent
folder from before the engine (files at its top: Job_Search_Tracker.xlsx,
Job_Search_Notes.txt, rejection_patterns.csv, scripts/employers.json and the
documents in output_files_gitignore/). The old folder is only read.

- Tracker: both trackers are combined by posting (link and title). When a
  posting is in both, the more decided row is kept (rejected or expired over
  accepted over new); on a tie the row already here is kept. Empty cells are
  filled from the other row.
- Rejection log: rows not already here are added, so later searches learn
  from them.
- Notes: the old notes are added once, under a dated heading.
- Employers to watch: employers not already listed are added; known ones
  get any extra careers-page links.
- Documents: CVs, cover letters and job-ad PDFs are copied into output/CV,
  output/CL and output/JD; a file with the same name here is left alone.
- The decisions file is not imported: those decisions are already in the
  old tracker's rows.

Before anything changes, the files here that will change are copied to
backups/<date_time>_import/. Running it again adds nothing twice.
"""
import csv
import hashlib
import json
import os
import shutil
from datetime import date, datetime

from . import tracker as tr

DOC_KINDS = {"CV": "cv_out", "CL": "cl_out", "JD": "jd_out"}
DOC_EXT = (".docx", ".pdf", ".doc", ".odt", ".txt", ".md")


def _first(*paths):
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


def locate(src):
    """Finds the parts of an old agent folder. Returns {part: path or list}."""
    src = os.path.abspath(os.path.expanduser(src))
    j = lambda *a: os.path.join(src, *a)
    over = {}
    try:
        with open(j("agent_home.json"), encoding="utf-8") as f:
            over = (json.load(f) or {}).get("paths", {}) or {}
    except (OSError, ValueError):
        pass
    o = lambda key: j(over[key]) if key in over else None
    found = {
        "tracker": _first(o("tracker"), j("state", "Job_Search_Tracker.xlsx"), j("Job_Search_Tracker.xlsx")),
        "notes": _first(o("notes"), j("state", "Job_Search_Notes.txt"), j("Job_Search_Notes.txt")),
        "rejection_log": _first(o("rejection_log"), j("state", "rejection_patterns.csv"), j("rejection_patterns.csv")),
        "employers": _first(o("employers"), j("inputs", "employers.json"), j("scripts", "employers.json"), j("employers.json")),
        "documents": {},
    }
    # documents: kind folders (output/CV, output_files_gitignore/CV ...) or one flat folder of CV_/CL_/JD_ files
    for kind, key in DOC_KINDS.items():
        files = []
        for d in (o(key), j("output", kind), j("output_files_gitignore", kind)):
            if d and os.path.isdir(d):
                files += [os.path.join(d, n) for n in sorted(os.listdir(d)) if n.lower().endswith(DOC_EXT)]
        flat = j("output_files_gitignore")
        if os.path.isdir(flat):
            files += [os.path.join(flat, n) for n in sorted(os.listdir(flat))
                      if n.upper().startswith(kind + "_") and n.lower().endswith(DOC_EXT) and os.path.isfile(os.path.join(flat, n))]
        found["documents"][kind] = list(dict.fromkeys(files))
    return found


# ------------------------------------------------------------------ tracker
def _norm_url(u):
    u = str(u or "").strip()
    for pre in ("https://", "http://"):
        if u.lower().startswith(pre):
            u = u[len(pre):]
    u = u.split("#")[0].rstrip("/")
    if u.lower().startswith("www."):
        u = u[4:]
    return u.lower()


def _key(row):
    return (_norm_url(row.get("URL")), " ".join(str(row.get("Title") or "").lower().split()))


def _rank(row):
    s = str(row.get("Status") or "")
    if tr.status_bucket(s) in ("rejected", "expired"):
        return 3
    if s.startswith("Approved") or s.startswith("Applied"):
        return 2
    return 1


def merge_rows(here, old):
    """Combines two lists of tracker rows. Returns (rows, {"added": n, "decided": n, "same": n})."""
    out, index = [], {}
    for r in here:
        k = _key(r)
        if k in index:
            continue
        index[k] = len(out)
        out.append(dict(r))
    added = decided = same = 0
    for r in old:
        k = _key(r)
        if k not in index:
            index[k] = len(out)
            out.append(dict(r))
            added += 1
            continue
        mine = out[index[k]]
        if _rank(r) > _rank(mine):
            keep, other = dict(r), mine
            decided += 1
        else:
            keep, other = mine, r
            same += 1
        for f, v in other.items():
            if keep.get(f) in (None, "") and v not in (None, ""):
                keep[f] = v
        out[index[k]] = keep
    return out, {"added": added, "decided": decided, "same": same}


# ------------------------------------------------------------------ small files
def _read_csv(path):
    if not path or not os.path.isfile(path):
        return [], []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return (rows[0], rows[1:]) if rows else ([], [])


def _employers(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError, TypeError):
        return None
    if isinstance(d, list):
        d = {"employers": d}
    return d if isinstance(d, dict) else None


def _norm_name(n):
    return " ".join(str(n or "").lower().split())


# ------------------------------------------------------------------ the import
def plan(home, src):
    """What an import would do, without changing anything."""
    return run(home, src, dry_run=True)


def run(home, src, dry_run=False):
    src = os.path.abspath(os.path.expanduser(src))
    root = os.path.realpath(home.root)
    if not os.path.isdir(src):
        raise ValueError(f"no such folder: {src}")
    if os.path.realpath(src) == root:
        raise ValueError("that is this agent home itself")
    found = locate(src)
    if not any([found["tracker"], found["notes"], found["rejection_log"], found["employers"]] + list(found["documents"].values())):
        raise ValueError(f"no agent files found in {src}")

    report = {"source": src, "dry_run": dry_run, "found": {k: (v if k != "documents" else {d: len(f) for d, f in v.items()})
                                                          for k, v in found.items()}}
    changes = []   # (target path, writer) run after the backup

    # tracker
    t_path = home.path("tracker")
    if found["tracker"]:
        here = tr.read_all_rows(t_path)
        old, _ = merge_rows([], tr.read_all_rows(found["tracker"]))   # a posting listed twice there counts once
        rows, stats = merge_rows(here, old)
        stats.update(here=len(here), old=len(old), total=len(rows))
        report["tracker"] = stats
        if stats["added"] or stats["decided"] or (stats["same"] and rows != here):
            def write_tracker(rows=rows):
                tmp = t_path + ".import.xlsx"
                if os.path.exists(tmp):
                    os.remove(tmp)
                tr.update(tmp, rows, seniority_cfg=home.search_config().get("seniority"))
                os.replace(tmp, t_path)
            changes.append((t_path, write_tracker))

    # rejection log
    r_path = home.path("rejection_log")
    if found["rejection_log"]:
        head_here, rows_here = _read_csv(r_path)
        head_old, rows_old = _read_csv(found["rejection_log"])
        head = head_here or head_old
        if head_old and head_here and head_old != head_here:
            # same columns by name, in this folder's order
            pos = {h: i for i, h in enumerate(head_old)}
            rows_old = [[r[pos[h]] if h in pos and pos[h] < len(r) else "" for h in head_here] for r in rows_old]
        seen = {tuple(r) for r in rows_here}
        new = [r for r in rows_old if tuple(r) not in seen and any(c.strip() for c in r)]
        new = [r for i, r in enumerate(new) if tuple(r) not in {tuple(x) for x in new[:i]}]
        report["rejection_log"] = {"here": len(rows_here), "added": len(new)}
        if new:
            def write_rejections(head=head, rows=rows_here + new):
                rows = sorted(rows, key=lambda r: r[0] if r else "")
                os.makedirs(os.path.dirname(r_path), exist_ok=True)
                with open(r_path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(head)
                    w.writerows(rows)
            changes.append((r_path, write_rejections))

    # notes
    n_path = home.path("notes")
    if found["notes"]:
        with open(found["notes"], encoding="utf-8", errors="replace") as f:
            old_text = f.read().strip()
        try:
            with open(n_path, encoding="utf-8", errors="replace") as f:
                here_text = f.read()
        except OSError:
            here_text = ""
        mark = "import " + hashlib.sha1(old_text.encode("utf-8")).hexdigest()[:12]
        todo = bool(old_text) and mark not in here_text
        report["notes"] = {"added": todo, "characters": len(old_text) if todo else 0}
        if todo:
            def write_notes(old_text=old_text, mark=mark):
                os.makedirs(os.path.dirname(n_path), exist_ok=True)
                with open(n_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n===== Notes from the earlier agent ({os.path.basename(src)}), imported {date.today().isoformat()} [{mark}] =====\n\n")
                    f.write(old_text + "\n")
            changes.append((n_path, write_notes))

    # employers to watch
    e_path = home.path("employers")
    if found["employers"]:
        old = _employers(found["employers"]) or {}
        mine = _employers(e_path) or {"mode": "extend", "employers": [], "exclude": []}
        mine.setdefault("mode", "extend")
        mine.setdefault("employers", [])
        by_name = {_norm_name(e.get("name")): e for e in mine["employers"] if isinstance(e, dict)}
        added = links = 0
        for e in old.get("employers", []) or []:
            if not isinstance(e, dict) or not e.get("name"):
                continue
            urls = e.get("urls") or ([e["url"]] if e.get("url") else [])
            have = by_name.get(_norm_name(e["name"]))
            if not have:
                entry = {"name": e["name"], "urls": list(urls)}
                mine["employers"].append(entry)
                by_name[_norm_name(e["name"])] = entry
                added += 1
                continue
            have.setdefault("urls", [])
            for u in urls:
                if u not in have["urls"]:
                    have["urls"].append(u)
                    links += 1
        report["employers"] = {"added": added, "links_added": links}
        if added or links:
            def write_employers(mine=mine):
                os.makedirs(os.path.dirname(e_path), exist_ok=True)
                with open(e_path, "w", encoding="utf-8") as f:
                    json.dump(mine, f, indent=2, ensure_ascii=False)
                    f.write("\n")
            changes.append((e_path, write_employers))

    # documents
    docs = {}
    copies = []
    for kind, key in DOC_KINDS.items():
        dest = home.path(key)
        n = 0
        for p in found["documents"][kind]:
            target = os.path.join(dest, os.path.basename(p))
            if not os.path.exists(target) and target not in [c[1] for c in copies]:
                copies.append((p, target))
                n += 1
        docs[kind] = n
    report["documents"] = docs

    if dry_run:
        report["backup"] = None
        return report

    backup = None
    to_back = [p for p, _ in changes if os.path.exists(p)]
    if to_back:
        backup = os.path.join(root, "backups", datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_import")
        for p in to_back:
            rel = os.path.relpath(os.path.realpath(p), root)
            dest = os.path.join(backup, rel if not rel.startswith("..") else os.path.basename(p))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(p, dest)
    for _, write in changes:
        write()
    for p, target in copies:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(p, target)
    report["backup"] = backup
    return report


def describe(rep):
    """Plain-text lines for the terminal."""
    lines = [("Would import" if rep["dry_run"] else "Imported") + f" from {rep['source']}:"]
    t = rep.get("tracker")
    if t:
        lines.append(f"  tracker: {t['old']} posting(s) there, {t['here']} here -> {t['total']} in all "
                     f"({t['added']} new here, {t['decided']} now carry the earlier decision, {t['same']} already here)")
    else:
        lines.append("  tracker: none found")
    r = rep.get("rejection_log")
    lines.append(f"  rejection reasons: {r['added']} added" if r else "  rejection reasons: none found")
    n = rep.get("notes")
    lines.append(("  notes: added under a dated heading" if n["added"] else "  notes: already imported") if n else "  notes: none found")
    e = rep.get("employers")
    lines.append(f"  employers to watch: {e['added']} added, {e['links_added']} extra link(s)" if e else "  employers to watch: none found")
    d = rep.get("documents", {})
    lines.append(f"  documents: {d.get('CV', 0)} CV, {d.get('CL', 0)} cover letter, {d.get('JD', 0)} job ad file(s) copied")
    if rep.get("backup"):
        lines.append(f"  the files here that changed were first copied to {rep['backup']}")
    lines.append("  the earlier folder was only read")
    return lines
