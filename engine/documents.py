# Job-search agent engine
# File:    engine/documents.py
# Purpose: Template documents, document checks, rendering and JD snapshots.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
Tailored documents: CV, cover letter (CL) and job-description snapshot (JD).

Two modes, chosen automatically from what the agent home contains:

full      The candidate has a profile and/or uploaded CVs/letters. The agent
          writes a document spec (JSON, see docs/document_spec.md) from that
          material only, following skills/tailor-documents/SKILL.md, then
          './run.sh tailor render' turns it into .docx.

template  No candidate material (not even a name is required). The engine
          builds a template CV and CL for a hypothetical candidate from the
          posting's keywords: real section structure, [bracketed]
          placeholders and prompts saying what to write where. No experience
          is invented. Any profile fields that do exist (name, contact,
          education...) are filled in as given.

Rendering uses Node.js + the docx module when available, otherwise a
Markdown file is written instead, so the step never fails for lack of
tooling.
"""
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date

from . import doc_naming
from .home import REPO_DIR, docx_renderer_status

TEMPLATE_NOTE = ("Template generated from the posting's keywords. Replace every [bracketed] item with your own, "
                 "real information and delete anything that does not apply. Nothing in this template is a claim "
                 "about you.")
MAX_KEYWORDS = 8


def posting_keywords(row, limit=MAX_KEYWORDS, description=None, vocabulary=None):
    raw = str(row.get("Required Skills (summary)") or "")
    if "not extracted" in raw.lower():
        raw = ""
    if not raw.strip() and description:
        from .collect.match import skills_summary, default_vocabulary
        raw = skills_summary(description, list(vocabulary or []) + default_vocabulary(), limit=limit)
    parts = re.split(r"[,;/\n]|\band\b|\boch\b", raw)
    seen, out = set(), []
    for p in parts:
        k = p.strip(" .:-()").strip()
        if 1 < len(k) <= 60 and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out[:limit]


def _contact_line(identity):
    bits = [identity.get(k) for k in ("email", "phone", "location") if identity.get(k)]
    bits += [l for l in (identity.get("links") or []) if l]
    return "  |  ".join(bits) if bits else "[email]  |  [phone]  |  [city, country]"


def _entries_from_profile(items, kind):
    out = []
    for it in items:
        if kind == "education":
            title = it.get("degree") or ""
            org = ", ".join(x for x in (it.get("institution"), it.get("location")) if x)
            paras = [f"Thesis: {it['thesis']}"] if it.get("thesis") else []
            if it.get("note"):
                paras.append(it["note"])
            out.append({"title": title, "dates": _dates(it), "org": org, "paragraphs": paras})
        else:
            out.append({"title": it.get("title") or "", "dates": _dates(it),
                        "org": ", ".join(x for x in (it.get("organization"), it.get("location")) if x),
                        "bullets": list(it.get("bullets") or [])})
    return out


def _dates(it):
    end = "Present" if it.get("current") else (it.get("end") or "")
    start = it.get("start") or ""
    return f"{start} – {end}".strip(" –") if (start or end) else ""


def saved_description(home, url):
    """The posting description captured by 'collect', if any."""
    import glob
    for p in sorted(glob.glob(os.path.join(home.path("new_postings"), "collect_*.json")), reverse=True):
        try:
            with open(p, "r", encoding="utf-8") as f:
                for c in json.load(f).get("kept_candidates", []):
                    if c.get("url") == url and c.get("description"):
                        return c["description"]
        except (OSError, ValueError):
            continue
    return ""


def template_specs(row, profile=None, style=None, description=None, vocabulary=None):
    """CV and CL specs for a hypothetical candidate, built from the posting.
    Uses only profile fields that exist; everything else is a placeholder."""
    profile = profile or {}
    style = style or {}
    ident = profile.get("identity") or {}
    title = row.get("Title") or "[Position title]"
    employer = row.get("Employer") or "[Employer]"
    kws = posting_keywords(row, description=description, vocabulary=vocabulary)
    kw_text = ", ".join(kws) if kws else "[the main requirements listed in the posting]"
    name = ident.get("name") or "[Your name]"
    banner = {"name": name, "title": title,
              "subtitle": ident.get("headline") or "[Your highest degree or main qualification]",
              "contact": _contact_line(ident)}

    exp_bullets = [f"[What you did with {k}: the task, your own contribution, tools used, and the result]" for k in kws[:4]] or \
                  ["[A responsibility from this role that matches a requirement in the posting: what you did, your own part, tools, result]"]
    exp_bullets_2 = [f"[Experience with {k}, if you have it: what, where, your own part]" for k in kws[4:7]] or \
                    ["[A second relevant responsibility or project, described the same way]"]

    sections = [
        {"heading": "Profile", "paragraphs": [profile.get("summary") or
            f"[Two or three sentences: your professional identity and the experience that best matches {title} "
            f"at {employer}. The posting emphasizes: {kw_text}. Mention only what you have actually done.]"]},
        {"heading": "Work Experience", "entries": [
            {"title": "[Most recent job title]", "dates": "[Start – End or Present]", "org": "[Employer, city]", "bullets": exp_bullets},
            {"title": "[Previous job title]", "dates": "[Start – End]", "org": "[Employer, city]", "bullets": exp_bullets_2},
        ]},
        {"heading": "Technical Skills", "table": [[k, "[Your level, and where you used it]"] for k in kws] or
            [["[Skill area]", "[Tools, languages or methods, and where you used them]"]]},
    ]
    edu = profile.get("education") or []
    sections.append({"heading": "Education", "entries": _entries_from_profile(edu, "education") if edu else
                     [{"title": "[Degree, subject]", "dates": "[Start – End]", "org": "[Institution, city]",
                       "paragraphs": ["[Thesis or specialization, if relevant to the posting]"]}]})
    langs = profile.get("languages") or []
    sections.append({"heading": "Languages", "table": [[l.get("language", ""), l.get("level", "")] for l in langs] if langs else
                     [["[Language]", "[Level: native / fluent / professional / basic]"]]})
    sections.append({"heading": "References", "paragraphs": [profile.get("references") or "References available upon request."]})
    cv = {"type": "cv", "mode": "template", "template_note": TEMPLATE_NOTE, "banner": banner, "sections": sections}

    top = ", ".join(kws[:3]) if kws else "[the two or three most important requirements]"
    cl = {"type": "cl", "mode": "template", "template_note": TEMPLATE_NOTE,
          "banner": {"name": name, "title": title, "subtitle": "", "contact": banner["contact"]},
          "date": date.today().isoformat(),
          "recipient": [employer, ", ".join(dict.fromkeys(x.strip() for x in str(row.get("Location") or "[Location]").split(",") if x.strip()))],
          "salutation": "Dear Hiring Team,",
          "paragraphs": [
              f"[Opening: name the role ({title}) and state, in one or two sentences, the strongest real connection "
              f"between your background and what {employer} is asking for. Then a short bridge into why you are writing.]",
              f"[Evidence: pick the two or three experiences closest to {top}. For each: what was required, what you "
              f"personally did, the context (scale, tools, constraints) and the outcome.]",
              "[How you work: one or two real situations that show your working style in a way that matters for this role. "
              "Describe the situation rather than listing adjectives.]",
              f"[Motivation: why this specific role at {employer}, tied to the substance of the work described in the posting.]",
              "[Close: what you would contribute, in concrete terms, and that you would welcome a conversation.]",
          ],
          "closing": style.get("cl_closing") or "Kind regards,",
          "signature": ident.get("name") or "[Your name]"}
    return cv, cl


# --------------------------------------------------------------------- checks
def check_spec(spec, checks=None, style=None):
    """Mechanical checks; returns a list of problems (empty = passed)."""
    checks = checks or {}
    style = style or {}
    plain = spec_text(spec)
    problems = []
    if style.get("avoid_em_dash", True) and "—" in plain:
        problems.append("contains an em dash (style avoid_em_dash is on)")
    if spec.get("mode") != "template":
        left = re.findall(r"\[[^\]]{3,}\]", plain)
        if left:
            problems.append(f"{len(left)} unfilled [placeholder](s), e.g. {left[0]}")
    if not (spec.get("banner") or {}).get("name"):
        problems.append("banner has no name")
    kind = spec.get("type", "cv")
    for s in checks.get(f"{kind}_must_contain", []) or []:
        if s.lower() not in plain.lower():
            problems.append(f"missing required text: {s!r}")
    for s in checks.get("must_not_contain", []) or []:
        if s and s.lower() in plain.lower():
            problems.append(f"contains forbidden text: {s!r}")
    return problems


def spec_text(spec):
    parts = []
    b = spec.get("banner") or {}
    parts += [b.get(k, "") for k in ("name", "title", "subtitle", "contact")]
    for sec in spec.get("sections", []) or []:
        parts.append(sec.get("heading", ""))
        parts += sec.get("paragraphs", []) or []
        parts += sec.get("bullets", []) or []
        for e in sec.get("entries", []) or []:
            parts += [e.get("title", ""), e.get("dates", ""), e.get("org", "")]
            parts += e.get("paragraphs", []) or []
            parts += e.get("bullets", []) or []
        for r in sec.get("table", []) or []:
            parts += [str(x) for x in r]
    parts += spec.get("recipient", []) or []
    parts += [spec.get(k, "") or "" for k in ("salutation", "closing", "signature", "date")]
    parts += spec.get("paragraphs", []) or []
    return "\n".join(p for p in parts if p)


# ------------------------------------------------------------------ rendering
def render(spec, out_docx, style=None, style_path=None):
    """Writes out_docx via Node, or a .md fallback. Returns the written path."""
    os.makedirs(os.path.dirname(os.path.abspath(out_docx)), exist_ok=True)
    ok, _ = docx_renderer_status()
    if ok:
        tmp = tempfile.mkdtemp(prefix="jobagent_render_")
        tmp_spec = os.path.join(tmp, "spec.json")
        with open(tmp_spec, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
        cmd = [shutil.which("node"), os.path.join(REPO_DIR, "engine", "templates", "render_docx.js"), tmp_spec, out_docx]
        if style is not None:
            tmp_style = os.path.join(tmp, "style.json")
            with open(tmp_style, "w", encoding="utf-8") as f:
                json.dump(style, f)
            cmd.append(tmp_style)
        elif style_path:
            cmd.append(style_path)
        r = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)
        if r.returncode == 0:
            return out_docx
        print(f"[warn] docx rendering failed, writing Markdown instead: {r.stderr.strip()[:300]}")
    md_path = os.path.splitext(out_docx)[0] + ".md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(spec))
    return md_path


def to_markdown(spec):
    b = spec.get("banner") or {}
    lines = [f"# {b.get('name', '')}", f"**{b.get('title', '')}**"]
    if b.get("subtitle"):
        lines.append(b["subtitle"])
    lines += [b.get("contact", ""), ""]
    if spec.get("template_note"):
        lines += [f"_{spec['template_note']}_", ""]
    if spec.get("type") == "cl":
        for k in ("date",):
            if spec.get(k):
                lines += [spec[k], ""]
        lines += (spec.get("recipient") or []) + [""]
        if spec.get("salutation"):
            lines += [spec["salutation"], ""]
        for p in spec.get("paragraphs") or []:
            lines += [p, ""]
        lines += [spec.get("closing") or "Kind regards,", "", spec.get("signature") or b.get("name", "")]
    else:
        for sec in spec.get("sections") or []:
            lines += [f"## {sec.get('heading', '')}", ""]
            for p in sec.get("paragraphs") or []:
                lines += [p, ""]
            for e in sec.get("entries") or []:
                lines.append(f"**{e.get('title', '')}**  {e.get('dates', '')}")
                if e.get("org"):
                    lines.append(f"_{e['org']}_")
                lines += [p for p in e.get("paragraphs") or []]
                lines += [f"- {x}" for x in e.get("bullets") or []]
                lines.append("")
            for r in sec.get("table") or []:
                lines.append(f"- **{r[0]}**: {r[1] if len(r) > 1 else ''}")
            lines += [f"- {x}" for x in sec.get("bullets") or []]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------- JD snapshot
def jd_snapshot(row, out_pdf, full_text=None):
    """Writes the job description as HTML next to out_pdf and converts it to
    PDF when a converter is available. Returns the path written."""
    os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
    html_path = os.path.splitext(out_pdf)[0] + ".html"
    meta = [("Employer", row.get("Employer")), ("Title", row.get("Title")), ("Location", row.get("Location")),
            ("Announced", row.get("Announce Date")), ("Deadline", row.get("Deadline")),
            ("Work arrangement", row.get("Remote/Hybrid/Onsite")), ("URL", row.get("URL")),
            ("Snapshot taken", date.today().isoformat())]
    body = html.escape(full_text) if full_text else html.escape(str(row.get("Required Skills (summary)") or "")) + \
        "<p><em>Full description not captured; only the tracker summary is shown.</em></p>"
    doc = ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>JD snapshot</title>"
           "<style>body{font-family:Arial,sans-serif;max-width:780px;margin:32px auto;color:#222;font-size:13px}"
           "h1{font-size:18px;color:#1B3A5C}table{border-collapse:collapse;margin-bottom:18px}"
           "td{padding:3px 10px 3px 0;vertical-align:top}td:first-child{color:#666}pre{white-space:pre-wrap;font-family:inherit}</style>"
           "</head><body>"
           f"<h1>{html.escape(str(row.get('Title') or ''))} - {html.escape(str(row.get('Employer') or ''))}</h1><table>"
           + "".join(f"<tr><td>{k}</td><td>{html.escape(str(v or ''))}</td></tr>" for k, v in meta)
           + f"</table><pre>{body}</pre></body></html>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc)
    if _html_to_pdf(html_path, out_pdf):
        try:
            os.remove(html_path)
        except OSError:
            pass
        return out_pdf
    return html_path


def _html_to_pdf(html_path, pdf_path):
    candidates = [shutil.which(c) for c in ("google-chrome", "chromium", "chromium-browser", "chrome")]
    mac_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(mac_chrome):
        candidates.append(mac_chrome)
    for c in [c for c in candidates if c]:
        try:
            r = subprocess.run([c, "--headless", "--disable-gpu", f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer",
                                "file://" + os.path.abspath(html_path)], capture_output=True, timeout=90)
            if r.returncode == 0 and os.path.exists(pdf_path):
                return True
        except Exception:
            continue
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        try:
            outdir = os.path.dirname(os.path.abspath(pdf_path))
            r = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", outdir, html_path],
                               capture_output=True, timeout=120)
            produced = os.path.splitext(html_path)[0] + ".pdf"
            if r.returncode == 0 and os.path.exists(produced):
                if produced != pdf_path:
                    os.replace(produced, pdf_path)
                return True
        except Exception:
            pass
    return False


def filenames_for(row):
    return doc_naming.build_filenames(row.get("Employer"), row.get("Title"), row.get("Location"), url=row.get("URL"))
