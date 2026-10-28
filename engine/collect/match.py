# Job-search agent engine
# File:    engine/collect/match.py
# Purpose: Rule-based relevance, location, seniority, category and arrangement detection for collected postings.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
Deterministic first-pass judgement, so collection works without any AI.
The optional AI enrichment step (engine/enrich.py) or the agent can refine
it later; every automatic value is marked in Notes.
"""
import html
import re
import unicodedata

GENERIC_TOKENS = {
    "engineer", "engineers", "developer", "developers", "designer", "design", "specialist", "expert",
    "utvecklare", "ingenjor", "ingenjör", "konstruktor", "konstruktör", "senior", "junior", "lead",
    "of", "and", "the", "for", "och", "i", "in",
}

COUNTRY_NAMES = {
    "SE": ["sweden", "sverige"], "DK": ["denmark", "danmark"], "NO": ["norway", "norge"],
    "FI": ["finland", "suomi"], "DE": ["germany", "deutschland"], "NL": ["netherlands", "nederland"],
}

SENIORITY_PATTERNS = [
    ("Principal", r"\bprincipal\b"),
    ("Staff", r"\bstaff\b"),
    ("Lead", r"\b(lead|tech lead|team lead)\b"),
    ("Architect", r"\barchitect\b"),
    ("Senior", r"\b(senior|sr\.?)\b"),
    ("Graduate", r"\b(graduate|new grad|trainee|intern|internship|thesis|exjobb|praktik)\b"),
    ("Entry", r"\b(junior|jr\.?|entry[- ]level)\b"),
]

ACADEMIA_HINTS = {
    "Academia - Postdoc/Researcher": r"\b(postdoc|post-doc|postdoctoral|researcher|forskare|research fellow)\b",
    "Academia - Lecturer/Assistant Professor": r"\b(lecturer|lektor|assistant professor|biträdande lektor|professor)\b",
    "Academia - Research Engineer/Assistant": r"\b(research engineer|forskningsingenjör|research assistant|forskningsassistent)\b",
}


def fold(s):
    """Lowercase, strip accents (Västerås -> vasteras), collapse whitespace."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def strip_html(s):
    s = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", str(s or ""), flags=re.I)
    s = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t]+", " ", html.unescape(html.unescape(s))).strip()


def keyword_tokens(keyword):
    toks = [t for t in re.split(r"[^\w+#/.-]+", fold(keyword)) if t]
    core = [t for t in toks if t not in GENERIC_TOKENS]
    return core or toks


def _has(token, text):
    return re.search(r"(?<![\w])" + re.escape(token) + r"(?![\w])", text) is not None


def match_keywords(title, description, keywords, scope="title_or_description", exclude_terms=()):
    """Returns (matched_keywords, where) with where in {'title', 'description', None}."""
    t, d = fold(title), fold(description)
    for ex in exclude_terms or []:
        if ex and _has(fold(ex), t):
            return [], None
    in_title, in_desc = [], []
    # A description-only match also needs a role word from the keyword in the
    # title (e.g. "engineer", "design"), so a sales role that mentions FPGA
    # once is not picked up.
    title_role = re.search(r"(design|develop|engineer|ingenj|utveckl|konstrukt|architect|research)", t)
    for kw in keywords:
        toks = keyword_tokens(kw)
        if not toks:
            continue
        if all(_has(x, t) for x in toks):
            in_title.append(kw)
        elif scope == "title_or_description" and title_role and all(_has(x, d) for x in toks):
            in_desc.append(kw)
    if in_title:
        return in_title, "title"
    if in_desc:
        return in_desc, "description"
    return [], None


def location_names(loc):
    if isinstance(loc, str):
        return [fold(loc)]
    names = [loc.get("name", "")] + list(loc.get("aliases", []) or [])
    return [fold(n) for n in names if n]


def countries(locations):
    out = set()
    for l in locations:
        if isinstance(l, dict) and l.get("country"):
            out.update(COUNTRY_NAMES.get(str(l["country"]).upper(), [fold(l["country"])]))
    return out


def match_location(location_text, locations, remote_ok=True, is_remote=False):
    """Returns the matched location name, 'remote', or None."""
    lt = fold(location_text)
    for l in locations:
        for n in location_names(l):
            if n and _has(n, lt):
                return l["name"] if isinstance(l, dict) else l
    if remote_ok and (is_remote or re.search(r"\bremote\b|\bdistans\b", lt)):
        cs = countries(locations)
        if not cs or any(c in lt for c in cs) or re.search(r"\b(europe|eu|emea|nordic|nordics|scandinavia)\b", lt):
            return "remote"
    return None


def seniority(title):
    t = fold(title)
    for label, pat in SENIORITY_PATTERNS:
        if re.search(pat, t):
            return label
    return "Not stated"


def arrangement(*texts):
    t = fold(" ".join(str(x or "") for x in texts))
    if re.search(r"\b(fully remote|remote[- ]first|100% remote|distansarbete|helt pa distans)\b", t) or re.search(r"^remote\b", t):
        return "Remote"
    if re.search(r"\bhybrid\b", t):
        return "Hybrid"
    if re.search(r"\b(on[- ]?site|onsite|arbete pa plats|in office)\b", t):
        return "Onsite"
    if re.search(r"\bremote\b", t):
        return "Remote"
    return "Not stated"


def category(title, description, categories, rules=None):
    """Configured rules first ({category: [terms]}), then academia hints,
    then the first industry-type category, else 'Other'."""
    t = fold(title) + " " + fold(description)[:2000]
    for cat, terms in (rules or {}).items():
        if any(_has(fold(x), t) for x in terms):
            return cat
    for cat, pat in ACADEMIA_HINTS.items():
        if cat in categories and re.search(pat, fold(title)):
            return cat
    for cat in categories:
        if cat.lower().startswith("industry"):
            return cat
    return "Other" if "Other" in categories or not categories else categories[0]


def skills_summary(description, vocabulary, limit=10):
    d = fold(description)
    found = []
    for term in vocabulary:
        ft = fold(term)
        if ft and _has(ft, d) and term not in found:
            found.append(term)
        if len(found) >= limit:
            break
    return ", ".join(found)


def norm_key(employer, title):
    return (re.sub(r"[^a-z0-9]+", "", fold(employer))[:40], re.sub(r"[^a-z0-9]+", "", fold(title)))
