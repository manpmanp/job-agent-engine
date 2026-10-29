# Job-search agent engine
# File:    engine/conventions.py
# Purpose: Picks the writing conventions for one posting's CV and cover letter: market (country), sector (industry or academia) and level (junior, mid, senior).
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.4
# Date:    2026-10-29

"""
A CV for a US chip company and a CV for a Swedish one are written
differently: page size, length, personal details, tone, metrics, closing.
This module resolves, for one tracker row:

    market  from the posting's location: your configured locations, then
            country names, then state/province codes; when none matches,
            search_config.document_market (default "international")
    sector  "academia" if the Category starts with "Academia" or the title
            names an academic position, else "industry"
    level   from the Seniority Level (or the title): junior, mid or senior

and merges engine/defaults/document_conventions.json (market, then sector,
then level) with your own inputs/document_conventions.json on top.

    for_row(home, row) -> dict   (see keys below)
    as_text(conv)      -> the block given to the AI and the agent
"""
import copy
import json
import os
import re

from .collect.match import fold, seniority as title_seniority
from .home import DEFAULTS_DIR, _read_json, _strip_help

ACADEMIC_TITLE = re.compile(
    r"\b(postdoc|post-doc|postdoctoral|phd|ph\.d|doctoral|doktorand|research fellow|researcher|forskare|"
    r"lecturer|lektor|professor|faculty|tenure)\b")
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


def sector_of(row):
    if str(row.get("Category") or "").lower().startswith("academia"):
        return "academia"
    return "academia" if ACADEMIC_TITLE.search(fold(row.get("Title"))) else "industry"


def level_of(row, sector):
    label = str(row.get("Seniority Level") or "").strip()
    if not label or label == "Not stated":
        label = title_seniority(row.get("Title"))
    title = fold(row.get("Title"))
    if sector == "academia":
        if re.search(r"\b(professor|associate professor|senior lecturer|universitetslektor|docent|faculty)\b", title) \
                and "assistant professor" not in title:
            return "senior"
        if re.search(r"\b(phd|ph\.d|doctoral|doktorand|research assistant|forskningsassistent)\b", title):
            return "junior"
        return "mid"
    if any(l in label for l in SENIOR_LABELS):
        return "senior"
    if any(l in label for l in JUNIOR_LABELS):
        return "junior"
    return "mid"


def for_row(home, row, cfg=None, cat=None):
    """Merged conventions for one posting. Keys: market, sector, level,
    labels {market, sector, level}, country, cv_pages, page_size, letter
    {pages, salutation, closing, focus}, must_not_contain, and every text
    field of the market, sector and level."""
    cat = cat or catalogue(home)
    cfg = cfg if cfg is not None else home.search_config()
    fallback = str(cfg.get("document_market") or "").strip().lower()
    country = country_of(row.get("Location"), cat, cfg.get("locations"))
    market = _market_of_country(cat, country) or (fallback if fallback in cat["markets"] else "international")
    sector = sector_of(row)
    level = level_of(row, sector)
    m = cat["markets"][market]
    s = cat["sectors"].get(sector, {})
    lv = cat["levels"].get(level, {})
    conv = _deep_merge(m, {k: v for k, v in s.items() if k not in ("label", "cv_pages")})
    pages = (s.get("cv_pages") or m.get("cv_pages") or {}).get(level, "")
    conv.update({
        "market": market, "sector": sector, "level": level, "country": country,
        "labels": {"market": m.get("label", market), "sector": s.get("label", sector), "level": lv.get("label", level)},
        "cv_pages": pages, "level_emphasis": lv.get("emphasis", ""), "older_roles": lv.get("older_roles", ""),
        "sector_emphasis": s.get("emphasis", ""),
        "must_not_contain": list(m.get("must_not_contain") or []),
    })
    conv.pop("countries", None)
    conv.pop("emphasis", None)
    return conv


def summary(conv):
    """One line for the app and the CLI."""
    l = conv["labels"]
    return (f"{l['market']}; {conv['sector']}; {conv['level']}: {conv.get('page_size', 'A4')}, "
            f"CV {conv.get('cv_pages') or '?'} page(s), letter closes '{(conv.get('letter') or {}).get('closing', '')}'")


def as_text(conv):
    """The conventions as a plain block for a prompt or the agent."""
    l = conv["labels"]
    letter = conv.get("letter") or {}
    lines = [
        f"Market: {l['market']} (country: {conv.get('country') or 'not detected'})",
        f"Sector: {l['sector']}",
        f"Level: {l['level']}",
        f"Page size: {conv.get('page_size', 'A4')}",
        f"Spelling: {conv.get('spelling', '')}",
        f"Dates: {conv.get('date_format', '')}",
        f"CV length: {conv.get('cv_pages') or 'as needed'} page(s)" + (f" ({conv['cv_kind']})" if conv.get("cv_kind") else ""),
        f"Photo: {conv.get('photo', '')}",
        f"Personal details: {conv.get('personal_details', '')}",
        f"Work authorization: {conv.get('work_authorization', '')}",
        f"Tone: {conv.get('tone', '')}",
        f"Metrics: {conv.get('metrics', '')}",
        f"Profile section: {conv.get('profile_section', '')}",
        f"References: {conv.get('references', '')}",
    ]
    if conv.get("sections"):
        lines.append("Typical sections: " + ", ".join(conv["sections"]))
    if conv.get("publications"):
        lines.append(f"Publications: {conv['publications']}")
    if conv.get("sector_emphasis"):
        lines.append(f"Sector emphasis: {conv['sector_emphasis']}")
    if conv.get("level_emphasis"):
        lines.append(f"Level emphasis: {conv['level_emphasis']}; older roles: {conv.get('older_roles', '')}")
    lines.append(f"Cover letter: {letter.get('pages', '1')} page(s); salutation {letter.get('salutation', '')}; "
                 f"closing {letter.get('closing', '')}; focus: {letter.get('focus', '')}")
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
