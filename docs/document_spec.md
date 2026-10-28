<!--
  Job-search agent engine
  File:    docs/document_spec.md
  Purpose: Format of the JSON specs that CVs and cover letters are rendered from.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.4.0
  Date:    2026-10-28
-->

# Document spec

CVs and cover letters are written as JSON specs and rendered by
`engine/docx_render.py` (python-docx). Content is data, so no per-application
code is needed and the same checks run on every document.

## CV

```json
{
  "type": "cv",
  "banner": {"name": "", "title": "", "subtitle": "", "contact": ""},
  "sections": [
    {"heading": "Profile", "paragraphs": ["..."]},
    {"heading": "Work Experience", "entries": [
      {"title": "Job title", "dates": "2022 – Present", "org": "Employer, City",
       "bullets": ["..."], "paragraphs": []}
    ]},
    {"heading": "Technical Skills", "table": [["Label", "Description"]]},
    {"heading": "Education", "page_break_before": false, "entries": []},
    {"heading": "References", "paragraphs": ["References available upon request."]}
  ]
}
```

A section can hold any mix of `paragraphs`, `entries`, `table` and
`bullets`, rendered in that order. `page_break_before` starts the section
on a new page.

## Cover letter

```json
{
  "type": "cl",
  "banner": {"name": "", "title": "", "subtitle": "", "contact": ""},
  "date": "2026-11-02",
  "recipient": ["Employer", "City"],
  "salutation": "Dear Hiring Team,",
  "paragraphs": ["...", "..."],
  "closing": "Kind regards,",
  "signature": ""
}
```

## Optional keys

- `mode`: `"full"` or `"template"`. In full mode `tailor check` reports
  leftover `[placeholders]`.
- `template_note`: a small grey line under the banner.

## Look

Colours, font and page size come from `inputs/document_style.json` (see
`inputs.md`). Default: navy banner with white text, blue uppercase section
headers with a thin rule, bold job title with right-aligned dates, italic
grey organization line, borderless two-column skills table, A4, Calibri.

## Output names

`CV_<Employer>_<Title>_<Location>[_<JobID>].docx`, `CL_...docx`,
`JD_...pdf`. The job ID is taken from the posting URL when one is present
and omitted otherwise; it is never invented. Template documents are
prefixed `TEMPLATE_`. Rendered specs are kept in `output/specs/`.
