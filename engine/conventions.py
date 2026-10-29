# Job-search agent engine
# File:    engine/conventions.py
# Purpose: Picks the writing conventions for one posting's CV and cover letter: market (country) and position type (six academic, four industry), suggested automatically and tunable.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.4
# Date:    2026-10-29

"""
A CV for a US chip company and a CV for a Swedish one are written
differently, and so are a postdoc CV and an ASIC engineer's CV in Lund.
For one tracker row this module resolves:

    market  from the posting's location: your configured locations, then
            country names, then state/province codes; when none matches,
            search_config.document_market (default "international")
    type    phd, postdoc, research_assistant, assistant_professor, professor,
            lecturer, internship, junior, mid_senior or senior, from the title,
            category and seniority

Both are suggestions: state/document_choices.json holds what you chose for
a posting in the app (Jobs > Accepted and documents). The market gives page size, personal
details, tone of the country, salutation and closing; the type gives the
sections (order, headings, length, focus), confidence, wording, emphasis
and letter focus. Your tuned types (Settings > Writing style) live in
inputs/document_conventions.json and replace the suggested ones.

    for_row(home, row) -> dict      as_text(conv) -> the block for the AI and the agent
"""
import copy
import json
import os
import re

from .collect.match import fold, seniority as title_seniority
from .home import DEFAULTS_DIR, _read_json, _strip_help

SENIOR_LABELS = {"Manager", "Principal", "Staff", "Lead", "Architect", "Senior"}
JUNIOR_LABELS = {"Graduate", "Entry"}


def _deep_merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def catalogue(home=None):
    with open(os.path.join(DEFAULTS_DIR, "document_conventions.json"), "r", encoding="utf-8") as f:
        data = _strip_help(json.load(f))
    if home is not None:
        user = _strip_help(_read_json(home.path("document_conventions"), {}) or {})
        data = _deep_merge(data, user)
    return data


def _market_of_country(cat, code):
    code = (code or "").upper()
    if code == "UK":
        code = "GB"
    for key, m in cat["markets"].items():
        if code and code in [c.upper() for c in m.get("countries", [])]:
            return key
    return None


def country_of(location, cat, locations=None):
    """ISO country code for a posting's location text, or None."""
    text = str(location or "")
    t = " " + fold(text) + " "
    for loc in locations or []:
        if not isinstance(loc, dict) or not loc.get("country"):
            continue
        names = [loc.get("name")] + list(loc.get("aliases") or [])
        if any(n and re.search(r"(?<![a-z])" + re.escape(fold(n)) + r"(?![a-z])", t) for n in names):
            return str(loc["country"]).upper()
    named = [(fold(n), code) for code, names in cat.get("country_names", {}).items() for n in names]
    named += [(fold(r), code) for code, regions in cat.get("regions", {}).items() for r in regions if len(r) > 3]
    for name, code in sorted(named, key=lambda x: -len(x[0])):  # "new south wales" before "wales"
        if re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", t):
            return code
    parts = [p.strip() for p in re.split(r"[,/|()]| - ", text) if p.strip()]
    for code, regions in cat.get("regions", {}).items():     # "Austin, TX", "Toronto, ON"
        if any(r in parts for r in regions if len(r) <= 3):
            return code
    for p in reversed(parts):                                  # "Lund, SE"
        if re.fullmatch(r"[A-Z]{2}", p) and _market_of_country(cat, p):
            return p
    return None


def type_of(row, cat):
    """The position type for a posting, from its title and category."""
    title = fold(row.get("Title"))
    category = fold(row.get("Category"))
    academic_cat = category.startswith("academia")
    has = lambda pat: re.search(pat, title)
    if has(r"\b(phd|ph\.d|doctoral|doktorand|doctorate)\b"):
        return "phd"
    if has(r"\b(postdoc|post-doc|postdoctoral|research fellow)\b"):
        return "postdoc"
    if has(r"\b(assistant professor|tenure[- ]track|bitradande (universitets)?lektor)\b"):
        return "assistant_professor"
    if has(r"\b(associate professor|full professor|professor|docent|chair in)\b"):
        return "professor"
    if has(r"\b(lecturer|universitetslektor|lektor|teaching fellow)\b"):
        return "lecturer"
    if has(r"\b(research assistant|forskningsassistent|forskningsingenjor)\b") or \
            (academic_cat and has(r"\b(research engineer|researcher|forskare|scientist)\b")):
        return "research_assistant"
    if academic_cat:
        if "lecturer" in category or "professor" in category:
            return "lecturer"
        if "postdoc" in category:
            return "postdoc"
        return "research_assistant"
    if has(r"\b(intern|internship|thesis|exjobb|examensarbete|praktik|summer (student|job))\b"):
        return "internship"
    label = str(row.get("Seniority Level") or "").strip()
    if not label or label == "Not stated":
        label = title_seniority(row.get("Title"))
    if any(l in label for l in SENIOR_LABELS):
        return "senior"
    if any(l in label for l in JUNIOR_LABELS):
        return "junior"
    return "mid_senior"


def posting_key(row):
    return f"{row.get('URL') or ''}||{row.get('Title') or ''}"


def choices(home):
    """Your per-posting choices: {posting key: {"type": ..., "market": ...}}."""
    return _read_json(home.path("document_choices"), {}) or {}


def set_choice(home, key, type_=None, market=None):
    """Saves (or clears, with empty values) the type and market of one posting."""
    data = choices(home)
    entry = {k: v for k, v in (("type", type_), ("market", market)) if v}
    if entry:
        data[key] = entry
    else:
        data.pop(key, None)
    path = home.path("document_choices")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    return data


def for_row(home, row, cfg=None, cat=None, picks=None):
    """Merged conventions for one posting: its market (country) and position
    type, each suggested automatically unless you chose one for this posting.
    Keys: market, type, group, level, country, auto {market, type}, chosen
    {market, type}, labels, cv_pages, page_size, sections [{id, heading,
    length, focus}], confidence (1-5), confidence_text, emphasis, wording,
    letter {pages, salutation, closing, focus}, must_not_contain, and the
    market's text fields."""
    cat = cat or catalogue(home)
    cfg = cfg if cfg is not None else home.search_config()
    picks = picks if picks is not None else (choices(home) if home is not None else {})
    pick = picks.get(posting_key(row)) or {}
    fallback = str(cfg.get("document_market") or "").strip().lower()
    country = country_of(row.get("Location"), cat, cfg.get("locations"))
    auto_market = _market_of_country(cat, country) or (fallback if fallback in cat["markets"] else "international")
    auto_type = type_of(row, cat)
    market = pick.get("market") if pick.get("market") in cat["markets"] else auto_market
    typ = pick.get("type") if pick.get("type") in cat["types"] else auto_type
    m, t = cat["markets"][market], cat["types"][typ]
    conv = copy.deepcopy(m)
    conv.pop("countries", None)
    level = t.get("level", "mid")
    conf = int(t.get("confidence") or 3)
    conv.update({
        "market": market, "type": typ, "group": t.get("group", "industry"), "sector": t.get("group", "industry"),
        "level": level, "country": country,
        "auto": {"market": auto_market, "type": auto_type},
        "chosen": {"market": market != auto_market, "type": typ != auto_type},
        "labels": {"market": m.get("label", market), "type": t.get("label", typ)},
        "cv_pages": t.get("cv_pages") or (m.get("cv_pages") or {}).get(level, ""),
        "sections": copy.deepcopy(t.get("sections") or []),
        "confidence": conf, "confidence_text": (cat.get("confidence") or {}).get(str(conf), ""),
        "emphasis": t.get("emphasis", ""), "wording": t.get("wording", ""),
        "extras": list(t.get("extras") or []),
        "letter": _deep_merge(m.get("letter") or {}, t.get("letter") or {}),
        "lengths": cat.get("lengths") or {},
        "must_not_contain": list(m.get("must_not_contain") or []),
    })
    return conv


def summary(conv):
    """One line for the app and the CLI."""
    l = conv["labels"]
    return (f"{l['market']}; {l['type']}: {conv.get('page_size', 'A4')}, "
            f"CV {conv.get('cv_pages') or '?'} page(s), letter closes '{closing(conv)}'")


def as_text(conv):
    """The conventions as a plain block for a prompt or the agent."""
    l = conv["labels"]
    letter = conv.get("letter") or {}
    lengths = conv.get("lengths") or {}
    lines = [
        f"Market: {l['market']} (country: {conv.get('country') or 'not detected'})",
        f"Position type: {l['type']} ({conv.get('group')})",
        f"Page size: {conv.get('page_size', 'A4')}",
        f"Spelling: {conv.get('spelling', '')}",
        f"Dates: {conv.get('date_format', '')}",
        f"CV length: {conv.get('cv_pages') or 'as needed'} page(s)",
        f"Photo: {conv.get('photo', '')}",
        f"Personal details: {conv.get('personal_details', '')}",
        f"Work authorization: {conv.get('work_authorization', '')}",
        f"Tone of the market: {conv.get('tone', '')}",
        f"Confidence for this position type: {conv.get('confidence')}/5, {conv.get('confidence_text', '')}",
        f"Wording: {conv.get('wording', '')}",
        f"Emphasis: {conv.get('emphasis', '')}",
        f"Metrics: {conv.get('metrics', '')}",
        f"References in this market: {conv.get('references', '')}",
        "CV sections, in this order (use these headings; leave out a section the candidate has nothing real for):",
    ]
    for s in conv.get("sections") or []:
        if s.get("length") == "off":
            continue
        lines.append(f"  - {s['heading']} [{s.get('length', 'normal')}: {lengths.get(s.get('length'), '')}]"
                     + (f": {s['focus']}" if s.get("focus") else ""))
    off = [s["heading"] for s in conv.get("sections") or [] if s.get("length") == "off"]
    if off:
        lines.append("  Left out for this type: " + ", ".join(off))
    lines.append(f"Cover letter: {letter.get('pages', '1')} page(s); salutation {letter.get('salutation', '')}; "
                 f"closing {closing(conv)}; focus: {letter.get('focus', '')}")
    if conv.get("extras"):
        lines.append("Extra documents sometimes asked for: " + "; ".join(conv["extras"]))
    lines.append(f"Language: {conv.get('language', '')}")
    for n in conv.get("notes") or []:
        lines.append(f"Note: {n}")
    if conv.get("must_not_contain"):
        lines.append("Never include: " + ", ".join(conv["must_not_contain"]) + " (checked)")
    lines.append("These are common practice. Where the posting asks for something specific, the posting wins; "
                 "the candidate's own rules (tailoring_rules.md) win over both.")
    return "\n".join(lines)


def editor_data(home):
    """What Settings > Writing style shows: the suggested type settings, your
    tuned ones, and the lists to choose from."""
    base = catalogue(None)
    mine = _strip_help(_read_json(home.path("document_conventions"), {}) or {}).get("types") or {}
    eff = catalogue(home)
    return {"types": eff["types"], "suggested": base["types"], "tuned": sorted(k for k in mine if k in base["types"]),
            "order": base["type_order"], "confidence": base["confidence"], "lengths": base["lengths"],
            "markets": {k: v.get("label", k) for k, v in base["markets"].items()}}


TYPE_FIELDS = ("cv_pages", "confidence", "emphasis", "wording", "sections", "letter")


def save_type(home, key, data):
    """Stores your version of one type (data None = back to the suggestion)."""
    base = catalogue(None)["types"]
    if key not in base:
        raise ValueError(f"unknown position type: {key}")
    path = home.path("document_conventions")
    user = _read_json(path, {}) or {}
    types = user.setdefault("types", {})
    if data is None:
        types.pop(key, None)
    else:
        clean = {k: data[k] for k in TYPE_FIELDS if k in data}
        secs = []
        for s in clean.get("sections") or []:
            h = str(s.get("heading") or "").strip()[:80]
            if h:
                ln = s.get("length") if s.get("length") in catalogue(None)["lengths"] else "normal"
                sid = re.sub(r"[^a-z0-9_]", "_", str(s.get("id") or h).lower())[:40]
                secs.append({"id": sid, "heading": h, "length": ln, "focus": str(s.get("focus") or "")[:300]})
        if "sections" in clean:
            clean["sections"] = secs
        if "confidence" in clean:
            clean["confidence"] = max(1, min(5, int(clean["confidence"])))
        if isinstance(clean.get("letter"), dict):
            clean["letter"] = {k: str(v)[:400] for k, v in clean["letter"].items() if k in ("pages", "focus")}
        for k in ("cv_pages", "emphasis", "wording"):
            if k in clean:
                clean[k] = str(clean[k])[:600]
        types[key] = clean
    if not types:
        user.pop("types", None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(user, f, indent=1, ensure_ascii=False)
    return editor_data(home)


def closing(conv):
    """The closing phrase alone, without the bracketed alternatives."""
    c = str((conv.get("letter") or {}).get("closing") or "Kind regards,")
    return re.split(r"\s*[(/]", c)[0].strip() or "Kind regards,"


def style_for(home, conv):
    """document_style with the market's page size and closing, unless your
    own inputs/document_style.json sets them."""
    style = dict(home.document_style())
    own = _strip_help(_read_json(home.path("document_style"), {}) or {})
    # The values older templates wrote ("A4", "Kind regards,") count as not set.
    if own.get("page_size") in (None, "", "A4") and conv.get("page_size"):
        style["page_size"] = conv["page_size"]
    if own.get("cl_closing") in (None, "", "Kind regards,"):
        style["cl_closing"] = closing(conv)
    return style


def checks_for(home, conv):
    """tailoring_checks plus the market's must_not_contain list."""
    checks = dict(home.tailoring_checks())
    extra = [x for x in conv.get("must_not_contain") or [] if x not in (checks.get("must_not_contain") or [])]
    checks["must_not_contain"] = list(checks.get("must_not_contain") or []) + extra
    return checks
