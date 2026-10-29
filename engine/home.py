# Job-search agent engine
# File:    engine/home.py
# Purpose: Agent-home paths, configuration merging and feature (capability) detection.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
Agent home: where a user's inputs, state and outputs live, and what the
engine can do with what is there.

The engine never stops because an optional input is missing. It works out
which features are available (capabilities()), runs those, and reports the
rest as "off" together with what would switch them on.

Layout of an agent home (every path can be overridden in agent_home.json,
which is how an existing folder layout is mapped without moving files):

    <home>/
      agent_home.json                  optional path overrides
      inputs/
        search_config.json             REQUIRED for the search service
        employers.json                 optional
        document_style.json            optional
        tailoring_rules.md             optional
        tailoring_checks.json          optional
        characteristics.md             optional
        references/                    optional, any files
        intake/cv/  intake/cl/         drop existing CVs / letters here;
                                       picked up by 'intake scan', the form's
                                       Update button and every run
        candidate/
          profile.json                 written by the engine (merged view)
          sources/                     every form / CV / letter you submitted
          history/                     earlier versions of profile.json
          conflicts.json               open conflicts between sources
      state/
        Job_Search_Tracker.xlsx
        Job_Search_Notes.txt
        rejection_patterns.csv
        decisions_sync.json
        new_postings/                  inbox: rows the search step found
        sync_logs/  search_progress/
      output/
        jobs-on-market.html
        weekly_summary/  specs/  CV/  CL/  JD/
"""
import json
import os
import shutil
import subprocess

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(ENGINE_DIR)
DEFAULTS_DIR = os.path.join(ENGINE_DIR, "defaults")                 # engine defaults, skill vocabulary, presets
INPUT_TEMPLATES_DIR = os.path.join(ENGINE_DIR, "templates", "inputs")  # blank inputs for a new agent home
STATE_TEMPLATES_DIR = os.path.join(ENGINE_DIR, "templates", "state")   # empty tracker, notes, logs
WEB_DIR = os.path.join(ENGINE_DIR, "web")                           # the app page and the input form
AGENT_DIR = os.path.join(REPO_DIR, "agent")                         # instructions for an optional AI agent
DEMO_DIR = os.path.join(REPO_DIR, "docs", "demo")                   # fictional demo data and example output

DEFAULT_PATHS = {
    "inputs": "inputs",
    "search_config": "inputs/search_config.json",
    "employers": "inputs/employers.json",
    "document_style": "inputs/document_style.json",
    "tailoring_rules": "inputs/tailoring_rules.md",
    "tailoring_checks": "inputs/tailoring_checks.json",
    "characteristics": "inputs/characteristics.md",
    "references": "inputs/references",
    "candidate": "inputs/candidate",
    "intake_cv": "inputs/intake/cv",
    "intake_cl": "inputs/intake/cl",
    "tracker": "state/Job_Search_Tracker.xlsx",
    "notes": "state/Job_Search_Notes.txt",
    "rejection_log": "state/rejection_patterns.csv",
    "decisions": "state/decisions_sync.json",
    "new_postings": "state/new_postings",
    "sync_logs": "state/sync_logs",
    "search_progress": "state/search_progress",
    "weekly_html": "output/jobs-on-market.html",
    "weekly_summary": "output/weekly_summary",
    "specs": "output/specs",
    "cv_out": "output/CV",
    "cl_out": "output/CL",
    "jd_out": "output/JD",
}


def _read_json(path, default=None):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError) as e:
        print(f"[warn] could not read {path}: {e}")
        return default


def _read_text(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _strip_help(d):
    if isinstance(d, dict):
        return {k: _strip_help(v) for k, v in d.items() if not k.startswith("_")}
    if isinstance(d, list):
        return [_strip_help(v) for v in d]
    return d


def _is_blank(v):
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, tuple)):
        return all(_is_blank(x) for x in v)
    if isinstance(v, dict):
        return all(_is_blank(x) for x in v.values())
    return False


def meaningful_text(text, template_name=None):
    """True if a markdown input holds real content: not empty and not just
    the unchanged template shipped in engine/templates/inputs/."""
    body = "\n".join(l.rstrip() for l in (text or "").strip().splitlines())
    if not body:
        return False
    if template_name:
        t = _read_text(os.path.join(INPUT_TEMPLATES_DIR, template_name))
        if body == "\n".join(l.rstrip() for l in t.strip().splitlines()):
            return False
    return any(l.strip() and not l.strip().startswith("#") for l in body.splitlines())


class Home:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        manifest = _read_json(os.path.join(self.root, "agent_home.json"), {}) or {}
        self.manifest = manifest
        overrides = manifest.get("paths", {}) or {}
        self.paths = {k: os.path.join(self.root, overrides.get(k, v)) for k, v in DEFAULT_PATHS.items()}

    def path(self, key):
        return self.paths[key]

    # ------------------------------------------------------------------ config
    def defaults(self):
        return _read_json(os.path.join(DEFAULTS_DIR, "search_defaults.json"), {}) or {}

    def search_config(self):
        """User search config merged over engine defaults. A key the user
        left blank keeps the default."""
        d = _strip_help(self.defaults())
        u = _strip_help(_read_json(self.path("search_config"), {}) or {})
        merged = dict(d)
        for k, v in u.items():
            if _is_blank(v) and k in d:
                continue
            if isinstance(v, dict) and isinstance(d.get(k), dict):
                sub = dict(d[k])
                sub.update({sk: sv for sk, sv in v.items() if not _is_blank(sv) or sk not in d[k]})
                merged[k] = sub
            else:
                merged[k] = v
        merged.setdefault("keywords", [])
        merged.setdefault("locations", [])
        merged.setdefault("weekly_list", {"enabled": True, "full_search_day": "Monday", "summary_markdown": True})
        return merged

    def document_style(self):
        style = {
            "font": "Calibri", "banner_color": "1F3864", "accent_color": "2E74B5",
            "secondary_text_color": "595959", "body_text_color": "222222",
            "page_size": "A4", "avoid_em_dash": True, "cl_closing": "Kind regards,",
        }
        user = _strip_help(_read_json(self.path("document_style"), {}) or {})
        style.update({k: v for k, v in user.items() if not _is_blank(v)})
        return style

    def tailoring_checks(self):
        c = {"cv_must_contain": [], "cl_must_contain": [], "must_not_contain": []}
        user = _strip_help(_read_json(self.path("tailoring_checks"), {}) or {})
        c.update({k: v for k, v in user.items() if isinstance(v, list)})
        return c

    def employers(self):
        """Final named-employer list: presets named in search_config, then
        the user's employers.json applied as extend or override, then
        exclusions."""
        cfg = self.search_config()
        result, order = {}, []
        for preset in cfg.get("employer_presets", []) or []:
            p = _read_json(os.path.join(DEFAULTS_DIR, "employer_presets", f"{preset}.json"))
            if not p:
                print(f"[warn] unknown employer preset '{preset}' (see engine/defaults/employer_presets/)")
                continue
            for e in p.get("employers", []):
                if e["name"] not in result:
                    order.append(e["name"])
                result[e["name"]] = e
        user = _strip_help(_read_json(self.path("employers"), {}) or {})
        user_list = [e for e in user.get("employers", []) if e.get("name")]
        if user.get("mode") == "override" and user_list:
            result, order = {}, []
        for e in user_list:
            if e["name"] not in result:
                order.append(e["name"])
            result[e["name"]] = e
        excluded = set(user.get("exclude", []) or [])
        return [result[n] for n in order if n not in excluded]

    # --------------------------------------------------------------- candidate
    def profile(self):
        return _read_json(os.path.join(self.path("candidate"), "profile.json"), {}) or {}

    def candidate_documents(self):
        src = os.path.join(self.path("candidate"), "sources")
        found = {"cv": [], "cl": []}
        for kind in found:
            d = os.path.join(src, kind)
            if os.path.isdir(d):
                names = set(os.listdir(d))
                found[kind] = sorted(os.path.join(d, f) for f in names
                                     if not f.startswith(".") and not (f.endswith(".txt") and f[:-4] in names))
        return found

    def reference_files(self):
        d = self.path("references")
        if not os.path.isdir(d):
            return []
        out = []
        for base, _, files in os.walk(d):
            out += [os.path.join(base, f) for f in files if not f.startswith(".")]
        return sorted(out)

    def candidate_name(self, fallback="the candidate"):
        return (self.profile().get("identity", {}) or {}).get("name") or fallback

    # ------------------------------------------------------------ capabilities
    def capabilities(self):
        """Returns {feature: (on: bool, reason: str)}. Never raises."""
        cfg = self.search_config()
        prof = self.profile()
        docs = self.candidate_documents()
        caps = {}

        has_kw = not _is_blank(cfg.get("keywords"))
        has_loc = not _is_blank(cfg.get("locations"))
        if has_kw and has_loc:
            caps["search"] = (True, f"{len(cfg['keywords'])} keyword(s) x {len(cfg['locations'])} location(s)")
        else:
            missing = [n for n, ok in (("keywords", has_kw), ("locations", has_loc)) if not ok]
            caps["search"] = (False, f"add {' and '.join(missing)} to {os.path.relpath(self.path('search_config'), self.root)}")

        wl = cfg.get("weekly_list", {}) or {}
        caps["weekly_list"] = (bool(wl.get("enabled", True)), "compiled from the tracker" if wl.get("enabled", True) else "disabled in search_config.weekly_list")
        caps["decision_sync"] = (True, "Accept/Reject on the weekly page, applied with './run.sh sync'")

        src = cfg.get("sources") or {}
        online = [n for n, k in (("Arbetsformedlingen API", "jobtech"), ("employer sites", "employer_sites")) if src.get(k, True)]
        if caps["search"][0] and online:
            caps["online_collection"] = (True, "built-in: " + ", ".join(online) + " ('./run.sh collect')")
        elif not online:
            caps["online_collection"] = (False, "all built-in sources disabled in search_config.sources")
        else:
            caps["online_collection"] = (False, "needs keywords and locations")
        try:
            from .enrich import status as _es
            caps["ai_enrichment"] = _es(self)
        except Exception as e:  # never break status
            caps["ai_enrichment"] = (False, f"unavailable: {e}")

        emps = self.employers()
        caps["named_employer_sweep"] = (bool(emps), f"{len(emps)} employer(s)" if emps else "add employer_presets or inputs/employers.json")

        has_exp = not _is_blank(prof.get("experience"))
        has_skills = not _is_blank(prof.get("skills"))
        has_level = not _is_blank((prof.get("preferences") or {}).get("own_seniority_level"))
        caps["fit_scoring"] = (has_exp or has_skills or has_level,
                               "uses candidate profile" if (has_exp or has_skills or has_level)
                               else "add a profile (form or CV) to score postings against the candidate")

        has_docs = bool(docs["cv"] or docs["cl"])
        if has_exp or has_docs:
            what = []
            if has_exp:
                what.append("profile")
            if docs["cv"]:
                what.append(f"{len(docs['cv'])} CV(s)")
            if docs["cl"]:
                what.append(f"{len(docs['cl'])} cover letter(s)")
            caps["tailoring_full"] = (True, "from " + ", ".join(what))
        else:
            caps["tailoring_full"] = (False, "add a CV ('./run.sh intake cv <file>') or a profile form; until then documents are templates")
        caps["tailoring_template"] = (True, "template documents built from posting keywords, no invented content")

        chars = meaningful_text(_read_text(self.path("characteristics")), "characteristics.md")
        caps["characteristics_tone"] = (chars, "used for cover-letter motivation" if chars else "optional: inputs/characteristics.md")
        rules = meaningful_text(_read_text(self.path("tailoring_rules")), "tailoring_rules.md")
        caps["personal_tailoring_rules"] = (rules, "inputs/tailoring_rules.md" if rules else "optional: inputs/tailoring_rules.md")
        refs = self.reference_files()
        caps["reference_material"] = (bool(refs), f"{len(refs)} file(s)" if refs else "optional: inputs/references/")

        cal = cfg.get("calendar", {}) or {}
        cal_on = bool(cal.get("enabled") and cal.get("calendar_id"))
        caps["calendar_deadlines"] = (cal_on, "locked to the configured calendar_id" if cal_on else "optional: search_config.calendar")

        conflicts = _read_json(os.path.join(self.path("candidate"), "conflicts.json"), []) or []
        open_c = [c for c in conflicts if not c.get("resolved")]
        caps["profile_conflicts"] = (not open_c, "none open" if not open_c else f"{len(open_c)} open, see './run.sh intake conflicts'")

        caps["docx_rendering"] = docx_renderer_status()
        return caps


def docx_renderer_status():
    try:
        import docx  # noqa: F401  (python-docx)
        return (True, "python-docx")
    except ImportError:
        return (False, "python-docx not installed (run setup); documents are written as Markdown until then")


def resolve_home(arg=None):
    root = arg or os.environ.get("JOB_AGENT_HOME") or os.path.join(REPO_DIR, "my_agent")
    return Home(root)
