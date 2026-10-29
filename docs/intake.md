<!--
  Job-search agent engine
  File:    docs/intake.md
  Purpose: How candidate data is added (forms or existing CVs) and merged.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.3.0
  Date:    2026-10-28
-->

# Candidate intake

Candidate data is optional and can be added, changed or extended at any
point while you use the agent. Every run reads the profile as it is at
that moment.

## Two routes, one profile

**Route 1: documents you already have.** A CV or cover letter you have
already sent somewhere.

```
./run.sh intake cv path/to/cv.pdf
./run.sh intake cl path/to/letter.docx
```

The original is stored in `inputs/candidate/sources/cv/` (or `cl/`) with
a timestamp, and its text is extracted next to it (`.docx` always, `.pdf`
when `pdftotext` or `pypdf` is available, `.txt`/`.md` as is). The source
shows as "awaiting extraction" until the agent has read it and submitted a
**fragment**: a JSON file in the profile format containing only what the
document states.

```
./run.sh intake fragment fragment.json --from cv-001
```

The original document remains the wording reference for tailoring.

**Route 1b: copy documents into the intake folders.** Every agent home has
two empty folders, `inputs/intake/cv/` and `inputs/intake/cl/`. Copy your
CVs and cover letters there and click **Update** in the form (tab 3), or run:

```
./run.sh intake scan
```

Every run also picks up new files there. A file is imported once (by its
content); the copy in the intake folder is left where it is.

**Route 2: a blank form.** Use the **Candidate profile** tab on the app's Setup page
(`./run.sh --setup` opens them and saves straight into your agent home), or
edit `inputs/candidate/profile_form.json` directly, then:

```
./run.sh intake form profile_form.json
```

The form can be loaded back into the page, changed and submitted again.

**Single fields:**

```
./run.sh intake set identity.email "alex@example.com"
./run.sh intake set languages '[{"language": "English", "level": "Fluent"}]'
```

## Profile format

`identity` (name, headline, email, phone, location, links,
work_authorization), `summary`, `experience[]` (title, organization,
location, start, end, current, bullets[], keywords[]), `education[]`
(degree, institution, location, start, end, thesis, note), `skills[]`
(group, items[]), `projects[]` (name, description, personal),
`publications[]` (title, venue, year, status, role), `training[]`,
`languages[]` (language, level), `references`, `preferences`
(own_seniority_level, target_roles[]). Every field is optional.

## How submissions are merged

`inputs/candidate/profile.json` is rebuilt from all submissions, oldest
to newest, after every intake command:

- `identity.*` and `preferences.*` merge field by field.
- `summary` and `references` are single values.
- List sections (`experience`, `education`, `skills`, `projects`,
  `publications`, `training`, `languages`) are taken as a whole from the
  newest submission that has entries for them.
- **The newest explicit entry wins.** Empty values never overwrite.
- When the new value replaces a different value that came from the other
  route (a CV-derived fragment versus a form or `set`), the change is
  recorded as a conflict:

```
./run.sh intake conflicts
./run.sh intake resolve 2 keep-previous     # or keep-new
```

`keep-previous` pins the earlier value; `keep-new` accepts the change.
Within one route (form after form) a newer entry is simply an update.

`profile.json` records which submission supplied each field
(`_sources`). Every earlier version is kept in
`inputs/candidate/history/`, and every submission in `sources/`, so any
change can be traced and undone.

## Without any candidate data

Accepted postings still get documents: `./run.sh tailor template`
produces a CV and cover letter for a hypothetical candidate, structured
around the posting's keywords, with placeholders for every personal
detail. If some profile fields exist (just a name, say), they are filled
in and the rest stays as placeholders.
