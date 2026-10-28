# Job-search agent engine
# File:    engine/doc_naming.py
# Purpose: File names for tailored documents (real job IDs only).
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
File names for tailored documents:

    CV_<EMPLOYER>_<TITLE>_<LOCATION>[_<JOBID>].docx
    CL_<...>.docx
    JD_<...>.pdf

JOBID is a real job reference taken from the posting URL (Workday R-number,
LinkedIn job-view ID, an id= query parameter, a long numeric path segment).
If none is found the segment is omitted. An ID is never invented.
"""
import re

JOB_ID_PATTERNS = [
    re.compile(r'_R-?\d+', re.IGNORECASE),
    re.compile(r'[?&]id=([A-Za-z0-9\-]+)'),
    re.compile(r'jobs/view/(\d+)'),
    re.compile(r'platsbanken/annonser/(\d+)'),
    re.compile(r'/(\d{6,})[/\-]'),
]


def extract_job_id(url):
    if not url:
        return None
    for p in JOB_ID_PATTERNS:
        m = p.search(url)
        if m:
            return (m.group(1) if m.groups() else m.group(0)).strip("_-")
    return None


def slugify(text):
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r'[\\/:*?"<>|]', "_", text)
    text = re.sub(r'\s+', "_", text)
    text = re.sub(r'[,;()&]', "_", text)
    text = re.sub(r'_+', "_", text)
    return text.strip("_")


_NOT_A_CITY = re.compile(
    r"^(sweden|sverige|denmark|danmark|norway|norge|finland|suomi|germany|deutschland|netherlands|"
    r"united kingdom|uk|usa|united states|europe|emea|remote|hybrid)$|\b(l[aä]n|county|kommun)$|^region\b",
    re.I)


def city_of(location):
    """The city part of a location string: 'Lund, Skåne län, Sverige',
    'Sweden - Lund' and 'Lund' all give 'Lund'. Countries, counties and
    regions are skipped; the first remaining part is used."""
    parts = [p.strip() for p in re.split(r"\s+-\s+|[,;/|]", str(location or "")) if p.strip()]
    for p in parts:
        if not _NOT_A_CITY.search(p):
            return p
    return parts[0] if parts else ""


def build_basename(employer, title, location, url=None, job_id=None):
    if job_id is None:
        job_id = extract_job_id(url)
    t = slugify(title)
    loc = slugify(city_of(location))
    if loc and loc.lower() in t.lower().split("_"):
        loc = ""  # the title already names the place
    parts = [slugify(employer), t, loc]
    if job_id:
        parts.append(slugify(job_id))
    return "_".join(p for p in parts if p)


def build_filenames(employer, title, location, url=None, job_id=None):
    base = build_basename(employer, title, location, url=url, job_id=job_id)
    return {"base": base, "cv": f"CV_{base}.docx", "cl": f"CL_{base}.docx", "jd": f"JD_{base}.pdf"}
