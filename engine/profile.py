# Job-search agent engine
# File:    engine/profile.py
# Purpose: Candidate intake: CV upload, forms, merging, conflicts and history.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
Candidate intake: optional, and possible at any time.

Two ways to provide candidate data, both ending in the same profile.json:

1. Prepared documents: a CV or cover letter already used for an
   application.
       ./run.sh intake cv path/to/cv.pdf
       ./run.sh intake cl path/to/letter.docx
   The original is stored under candidate/sources/ and its text extracted
   next to it. The agent then turns that text into a profile fragment
   (strictly what the document says, nothing added) and submits it with
       ./run.sh intake fragment fragment.json --from <source id>
   The original document also stays available as the wording reference for
   tailoring.

2. A blank form (engine/templates/inputs/candidate/profile_form.json, or
   the app's My CV and profile tab, which writes the same format):
       ./run.sh intake form my_profile.json

Single fields can be set directly:
       ./run.sh intake set identity.name "Alex Example"

Every submission is kept. profile.json is rebuilt from all of them:
- identity.* and preferences.* merge field by field; summary and
  references are single values; list sections (experience, education,
  skills, projects, publications, training, languages) are replaced as a
  whole by the newest submission that has entries for them.
- Newest explicit entry wins.
- When the newest value replaces a different value that came from a
  different kind of source (a CV versus a form, say), the change is
  recorded in conflicts.json for the user to confirm:
       ./run.sh intake conflicts
       ./run.sh intake resolve <n> keep-new | keep-previous
- Every rebuilt profile.json that differs from the last one is preceded by
  a copy of the previous version in candidate/history/.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone

SCALAR_FIELD_SECTIONS = ("identity", "preferences")
SCALAR_SECTIONS = ("summary", "references")
LIST_SECTIONS = ("experience", "education", "skills", "projects", "publications", "training", "languages")
KIND_GROUP = {"form": "manual", "set": "manual", "fragment": "document", "cv": "document", "cl": "document"}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _blank(v):
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, bool):
        return False
    if isinstance(v, (list, tuple)):
        return all(_blank(x) for x in v)
    if isinstance(v, dict):
        return all(_blank(x) for k, x in v.items() if k not in ("current", "personal"))
    return False


def _clean_list(items):
    return [i for i in (items or []) if not _blank(i)]


class Intake:
    def __init__(self, home):
        self.home = home
        self.dir = home.path("candidate")
        self.src_dir = os.path.join(self.dir, "sources")
        self.index_path = os.path.join(self.src_dir, "index.json")
        self.conflicts_path = os.path.join(self.dir, "conflicts.json")
        self.pins_path = os.path.join(self.dir, "pins.json")
        self.profile_path = os.path.join(self.dir, "profile.json")

    # ----------------------------------------------------------------- index
    def _index(self):
        if os.path.exists(self.index_path):
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_index(self, idx):
        os.makedirs(self.src_dir, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, ensure_ascii=False)

    def _register(self, kind, data_file=None, original=None, text_file=None, parent=None, note="", **extra):
        idx = self._index()
        sid = f"{kind}-{len(idx) + 1:03d}"
        entry = {"id": sid, "kind": kind, "submitted_at": _now(), "data_file": data_file,
                 "original": original, "text_file": text_file, "parent": parent, "note": note, **extra}
        idx.append(entry)
        self._save_index(idx)
        return entry

    # ---------------------------------------------------------------- intake
    def add_document(self, kind, path, quiet=False):
        """kind: 'cv' or 'cl'. Stores the original and extracted text.
        A file whose content was already imported is skipped."""
        if not os.path.exists(path):
            print(f"file not found: {path}")
            return None
        digest = _sha256(path)
        for e in self._index():
            if e.get("sha256") == digest:
                if not quiet:
                    print(f"already imported as {e['id']}: {os.path.basename(path)}")
                return None
        d = os.path.join(self.src_dir, kind)
        os.makedirs(d, exist_ok=True)
        stamp = _now()
        dest = os.path.join(d, f"{stamp}_{os.path.basename(path)}")
        shutil.copy2(path, dest)
        text = extract_text(dest)
        text_file = None
        if text:
            text_file = dest + ".txt"
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(text)
        entry = self._register(kind, original=os.path.relpath(dest, self.dir),
                               text_file=os.path.relpath(text_file, self.dir) if text_file else None,
                               note="awaiting extraction into a profile fragment", sha256=digest,
                               from_file=os.path.basename(path))
        if quiet:
            return entry
        print(f"stored {kind.upper()} as source {entry['id']}: {dest}")
        if text_file:
            print(f"extracted text: {text_file}")
        else:
            print("no text could be extracted automatically; the agent should read the original file directly")
        print(f"next: create a fragment from it (see docs/intake.md), then ./run.sh intake fragment <file> --from {entry['id']}")
        return entry

    def add_data(self, kind, path, parent=None):
        """kind: 'form' or 'fragment'. path: JSON in the profile format."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = {k: v for k, v in data.items() if not k.startswith("_")}
        d = os.path.join(self.src_dir, kind)
        os.makedirs(d, exist_ok=True)
        dest = os.path.join(d, f"{_now()}_{os.path.basename(path)}")
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        entry = self._register(kind, data_file=os.path.relpath(dest, self.dir), parent=parent)
        if parent:
            idx = self._index()
            for e in idx:
                if e["id"] == parent:
                    e["note"] = f"extracted into {entry['id']}"
            self._save_index(idx)
        print(f"stored {kind} as source {entry['id']}")
        return self.rebuild()

    def set_field(self, dotted, value):
        try:
            parsed = json.loads(value)
        except ValueError:
            parsed = value
        data = {}
        cur = data
        parts = dotted.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = parsed
        d = os.path.join(self.src_dir, "set")
        os.makedirs(d, exist_ok=True)
        dest = os.path.join(d, f"{_now()}_{re.sub(r'[^A-Za-z0-9_.-]', '_', dotted)}.json")
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._register("set", data_file=os.path.relpath(dest, self.dir))
        return self.rebuild()

    # ----------------------------------------------------------------- merge
    def rebuild(self):
        idx = [e for e in self._index() if e.get("data_file")]
        idx.sort(key=lambda e: e["submitted_at"])
        profile = {"schema_version": 1}
        origin = {}           # field -> (source_id, kind_group)
        conflicts = []

        def put(field, value, entry):
            group = KIND_GROUP.get(entry["kind"], entry["kind"])
            prev = origin.get(field)
            prev_val = _get(profile, field)
            if prev and not _blank(prev_val) and prev_val != value and prev[1] != group:
                conflicts.append({"field": field, "previous": {"value": prev_val, "source": prev[0]},
                                  "new": {"value": value, "source": entry["id"]}})
            _set(profile, field, value)
            origin[field] = (entry["id"], group)

        for entry in idx:
            with open(os.path.join(self.dir, entry["data_file"]), "r", encoding="utf-8") as f:
                data = json.load(f)
            for sec in SCALAR_FIELD_SECTIONS:
                for k, v in (data.get(sec) or {}).items():
                    if not _blank(v):
                        put(f"{sec}.{k}", v, entry)
            for sec in SCALAR_SECTIONS:
                if not _blank(data.get(sec)):
                    put(sec, data[sec], entry)
            for sec in LIST_SECTIONS:
                items = _clean_list(data.get(sec))
                if items:
                    put(sec, items, entry)

        pins = _load_json(self.pins_path, {})
        for field, value in pins.items():
            _set(profile, field, value)
            origin[field] = ("pinned", "manual")

        old = _load_json(self.conflicts_path, [])
        resolved = {(c["field"], c["new"]["source"]): c.get("resolved") for c in old if c.get("resolved")}
        for c in conflicts:
            r = resolved.get((c["field"], c["new"]["source"]))
            if r:
                c["resolved"] = r
            elif c["field"] in pins:
                c["resolved"] = "keep-previous"
        os.makedirs(self.dir, exist_ok=True)
        with open(self.conflicts_path, "w", encoding="utf-8") as f:
            json.dump(conflicts, f, indent=2, ensure_ascii=False)

        profile["_sources"] = {k: v[0] for k, v in sorted(origin.items())}
        profile["_built_at"] = _now()
        prev = _load_json(self.profile_path, None)
        if prev is not None and _strip_meta(prev) != _strip_meta(profile):
            hist = os.path.join(self.dir, "history")
            os.makedirs(hist, exist_ok=True)
            shutil.copy2(self.profile_path, os.path.join(hist, f"profile_{prev.get('_built_at', _now())}.json"))
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        open_c = [c for c in conflicts if not c.get("resolved")]
        print(f"profile rebuilt from {len(idx)} submission(s): {self.profile_path}")
        if open_c:
            print(f"{len(open_c)} conflict(s) need confirmation: ./run.sh intake conflicts")
        return profile

    def list_conflicts(self):
        cs = _load_json(self.conflicts_path, [])
        if not cs:
            return "No conflicts between sources."
        lines = []
        for i, c in enumerate(cs, start=1):
            state = c.get("resolved") or "OPEN"
            keep_prev = c.get("resolved") == "keep-previous"
            lines.append(f"[{i}] {c['field']} ({state})")
            lines.append(f"    previous ({c['previous']['source']}): {_short(c['previous']['value'])}{'   <- in use' if keep_prev else ''}")
            lines.append(f"    new      ({c['new']['source']}): {_short(c['new']['value'])}{'' if keep_prev else '   <- in use'}")
        return "\n".join(lines)

    def resolve(self, n, choice):
        cs = _load_json(self.conflicts_path, [])
        c = cs[int(n) - 1]
        pins = _load_json(self.pins_path, {})
        if choice == "keep-previous":
            pins[c["field"]] = c["previous"]["value"]
        elif choice == "keep-new":
            pins.pop(c["field"], None)
        else:
            raise SystemExit("choice must be keep-new or keep-previous")
        c["resolved"] = choice
        with open(self.pins_path, "w", encoding="utf-8") as f:
            json.dump(pins, f, indent=2, ensure_ascii=False)
        with open(self.conflicts_path, "w", encoding="utf-8") as f:
            json.dump(cs, f, indent=2, ensure_ascii=False)
        return self.rebuild()

    def sources(self):
        return self._index()

    def scan_intake_folders(self):
        """Imports every new CV / cover letter found in inputs/intake/cv and
        inputs/intake/cl. Files already imported (same content) are skipped,
        and the files in the intake folders are left where they are.
        Returns {"imported": [...], "skipped": [...], "unsupported": [...]}."""
        res = {"imported": [], "skipped": [], "unsupported": []}
        for kind in ("cv", "cl"):
            d = self.home.path(f"intake_{kind}")
            os.makedirs(d, exist_ok=True)
            for name in sorted(os.listdir(d)):
                path = os.path.join(d, name)
                if name.startswith(".") or not os.path.isfile(path):
                    continue
                if os.path.splitext(name)[1].lower() not in SUPPORTED_DOCS:
                    res["unsupported"].append(f"{kind}/{name}")
                    continue
                e = self.add_document(kind, path, quiet=True)
                if e:
                    res["imported"].append({"id": e["id"], "file": f"{kind}/{name}",
                                            "text_extracted": bool(e.get("text_file"))})
                else:
                    res["skipped"].append(f"{kind}/{name}")
        return res

    def folder_listing(self):
        """What is in the intake folders and whether each file is imported."""
        known = {e.get("sha256"): e["id"] for e in self._index() if e.get("sha256")}
        out = {}
        for kind in ("cv", "cl"):
            d = self.home.path(f"intake_{kind}")
            os.makedirs(d, exist_ok=True)
            items = []
            for name in sorted(os.listdir(d)):
                path = os.path.join(d, name)
                if name.startswith(".") or not os.path.isfile(path):
                    continue
                ok = os.path.splitext(name)[1].lower() in SUPPORTED_DOCS
                items.append({"file": name, "supported": ok, "imported_as": known.get(_sha256(path)) if ok else None})
            out[kind] = {"folder": d, "files": items}
        return out


# ------------------------------------------------------------------ helpers
SUPPORTED_DOCS = (".pdf", ".docx", ".txt", ".md")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _strip_meta(p):
    return {k: v for k, v in p.items() if k not in ("_built_at",)}


def _get(d, dotted):
    cur = d
    for p in dotted.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def _set(d, dotted, value):
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _short(v, n=110):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n] + "..."


_HEADING_WORDS = {
    "ABOUT", "ACADEMIC", "ACHIEVEMENTS", "ACTIVITIES", "ADDITIONAL", "AND", "AREAS", "AWARDS", "CAREER",
    "CERTIFICATES", "CERTIFICATIONS", "COMPETENCES", "COMPETENCIES", "CONTACT", "CONTRIBUTIONS", "CORE",
    "COURSES", "DETAILS", "EDUCATION", "EMPLOYMENT", "EXPERIENCE", "EXPERTISE", "GRANTS", "HIGHLIGHTS",
    "HISTORY", "HONORS", "HONOURS", "INFORMATION", "INTERESTS", "KEY", "KNOWLEDGE", "LANGUAGES",
    "LEADERSHIP", "ME", "OBJECTIVE", "OF", "OTHER", "PATENTS", "PERSONAL", "PROFESSIONAL", "PROFILE",
    "PROJECTS", "PUBLICATIONS", "QUALIFICATIONS", "REFERENCES", "RESEARCH", "SCIENTIFIC", "SELECTED",
    "SKILLS", "SUMMARY", "SUPERVISION", "TALKS", "TEACHING", "TECHNICAL", "TOOLS", "TRAINING",
    "VOLUNTEERING", "WORK",
    # Swedish
    "ARBETSLIVSERFARENHET", "ERFARENHET", "KOMPETENSER", "KUNSKAPER", "OCH", "PROFIL", "PUBLIKATIONER",
    "REFERENSER", "SAMMANFATTNING", "SPRÅK", "UTBILDNING", "ÖVRIGT",
}


def _segment_heading(letters):
    """Splits 'PROFESSIONALPROFILE' into known heading words, or None."""
    n = len(letters)
    best = [None] * (n + 1)
    best[0] = []
    for i in range(n):
        if best[i] is None:
            continue
        for j in range(i + 2, n + 1):
            if letters[i:j] in _HEADING_WORDS and best[j] is None:
                best[j] = best[i] + [letters[i:j]]
    return best[n]


def _join_spaced_headings(text):
    """Letter-spaced headings come out of PDFs split at random points:
    'PR OF ES SI ON AL PR OF ILE', 'EDU CATION', 'TECHN ICAL S KIL LS'.
    A line made only of upper-case letter groups is joined back when the
    letters split exactly into known heading words. Lines such as
    'AXI AHB APB' do not, so they are left as they are."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        frags = s.split()
        if 2 <= len(frags) <= 20 and len(s) <= 80 and all(f.isalpha() and f.isupper() for f in frags):
            words = _segment_heading("".join(frags))
            if words and len(words) < len(frags):
                line = " ".join(words)
        out.append(line)
    return "\n".join(out)


def extract_text(path):
    """Plain text from .docx (stdlib), .pdf (pdftotext or pypdf if present),
    .txt/.md. Returns '' when nothing could be extracted."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".txt", ".md"):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        if ext == ".docx":
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="replace")
            xml = re.sub(r"</w:p>", "\n", xml)
            xml = re.sub(r"<w:tab/>", "\t", xml)
            text = re.sub(r"<[^>]+>", "", xml)
            import html as _h
            return _h.unescape(text).strip()
        if ext == ".pdf":
            if shutil.which("pdftotext"):
                r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, timeout=60)
                if r.returncode == 0:
                    return _join_spaced_headings(r.stdout.decode("utf-8", errors="replace").strip())
            try:
                from pypdf import PdfReader  # optional
                return _join_spaced_headings("\n".join((p.extract_text() or "") for p in PdfReader(path).pages).strip())
            except Exception:
                return ""
    except Exception as e:
        print(f"[warn] text extraction failed for {path}: {e}")
    return ""
