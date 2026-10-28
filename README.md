<!--
  Job-search agent engine
  File:    README.md
  Purpose: What the project is, how it runs, and how to use it.
  Author:  manpmanp <manp.node@gmail.com>
  Code and documentation generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.4.0
  Date:    2026-10-28
-->

# Job-search agent engine

A local, file-based engine for an AI job-search agent. It searches for job
postings that match your keywords and locations, keeps every posting in a
tracker spreadsheet, gives you a weekly web page where you Accept or Reject
each one, and drafts a tailored CV, cover letter and job-description
snapshot for every posting you accept. It never applies, sends or posts
anything on your behalf.

The engine contains no personal data. Everything about you lives in your
own **agent home** folder and is read at run time. To start you only need
search keywords and locations. Everything else is optional and can be
added whenever you like.

---

## How it runs

The engine works on its own. An AI agent is optional and adds what the
engine cannot do by rules alone.

```
                       internet (public job data)
                                 |
        Arbetsformedlingen API, employer job boards (Greenhouse, Lever,
        Ashby, Workday, SmartRecruiters), employer career pages
                                 |
                                 v
 +-------------------------------------------+        +---------------------------+
 |  The engine   ./run.sh ...                |        |  Optional: an AI agent     |
 |  collect   fetch, match, classify, dedupe |  <---  |  (e.g. Claude) following   |
 |  verify    re-check that postings are open|        |  AGENT_PROMPT.md: adds     |
 |  sync      apply your Accept/Reject       |  --->  |  LinkedIn / Indeed, judges |
 |  weekly    weekly page + summary          |        |  unclear postings, writes  |
 |  tailor    CV / CL (template or full)     |        |  fully tailored CV / CL    |
 |  enrich    optional AI review via API key |        +---------------------------+
 +-------------------------------------------+
                  |  reads / writes
                  v
 +-------------------------------------------+        +---------------------------+
 |  Your agent home (private, on your disk)  | <----  |  You: forms, CV upload,    |
 |  inputs/  state/  output/                 |        |  Accept / Reject, review   |
 +-------------------------------------------+        +---------------------------+
```

### What the engine does by itself (no AI needed)

- **Collects postings online** (`./run.sh collect`):
  - Arbetsformedlingen's open JobSearch API (all of Platsbanken), one query
    per keyword.
  - Every employer in your list: through its job-board API when the
    careers URL belongs to Greenhouse, Lever, Ashby, Workday or
    SmartRecruiters; otherwise from the careers page itself, using its
    structured job data, or its job links as leads, which are then opened
    and read so they become confirmed postings with a description.
  - Optional aggregators, off by default: JSearch (Google for Jobs, which
    covers LinkedIn, Indeed and company sites, through your own API key),
    Adzuna (your key; 19 countries, not Sweden or Denmark), and Hacker
    News "Who is hiring?" and YC job posts (no key).
  - Keeps postings whose title matches a keyword (optionally also the
    description, see `match_scope`) and whose location matches one of
    yours, or that are remote if you accept remote.
  - Sets seniority, category, work arrangement and a skills summary by
    rules, and skips anything already tracked, so your decisions are never
    overwritten.
- **Reads any posting page** (`./run.sh fetch <url>`): the structured
  JobPosting data most job sites publish for search engines, else the
  page's main text without menus and footers, else, for pages built in
  the browser, a headless-browser render that waits for the page to settle.
  The text is kept for tailoring and the JD snapshot; `--add` tracks it.
- **Checks postings are still open** (`./run.sh verify`) and moves closed
  ones to Expired.
- **Builds the weekly page and summary**, applies your decisions, writes
  template documents for accepted postings.
- **Optional AI review** (`./run.sh enrich`) with your own Anthropic API
  key, to refine category, seniority and fit notes.
- **One command for a whole run**: `./run.sh run auto` does the full weekly
  pass on your search day and a sync on other days. `./run.sh schedule`
  prints the line to run it every morning (cron, or launchd on a Mac).

Every source is called politely: the engine names itself, waits between
requests to the same site, respects robots.txt (RFC 9309) for ordinary
pages, fetches pages only from public addresses, and only uses public job
data. Text read from pages is treated as data, never as instructions. A source that fails is reported and skipped; the run
always finishes.

### What an AI agent adds (optional)

LinkedIn and Indeed do not allow automated collection, so the engine
leaves them to an agent that reads them through its own tools, read-only.
The agent also judges unclear postings (unconfirmed leads, missing
locations, borderline seniority) and writes fully tailored CVs and cover
letters from your material. It uses the same commands, so engine and agent
share one tracker.

### A typical week

| When | Who | What happens |
|---|---|---|
| Every morning | engine (scheduled) | `run auto`: on your search day collect → verify → sync → weekly page; other days sync and templates |
| Search day, optional | agent | LinkedIn, Indeed, web search, judgement on new rows, tailored documents |
| Any time | you | open the weekly page, Accept or Reject, click **Sync decisions** |
| Any time | you | add or change candidate data with `intake` |

---

## What you get at each level of input

| You provide | You get |
|---|---|
| Keywords + locations | Online collection from Arbetsformedlingen, posting tracker, weekly page and summary, Accept/Reject sync, **template** CV/CL for accepted postings (structure and prompts built from the posting's keywords; nothing invented, no name needed) |
| + employer list or preset | Collection from each employer's job board or careers page, with a coverage report every run |
| + Anthropic API key (optional) | AI review of each collected posting |
| + profile (form) or an existing CV/CL | Fit notes on new postings, **tailored** CV/CL built only from your own material |
| + personal characteristics | Cover-letter motivation based on how you actually work |
| + personal tailoring rules / checks | Your mandatory entries and style rules, checked automatically |
| + document style | Your fonts and colours |

`./run.sh status` lists every feature as on or off, why, and what would
switch it on. A missing optional input is never an error.

---

## How to use it

### 1. Install and open the input forms

Requirements: Python 3.9 or newer, an internet connection for collection,
and Node.js for .docx output (without Node, documents are written as
Markdown).

```
git clone https://github.com/manpmanp/job-agent-engine.git
cd job-agent-engine
./run.sh --home ~/my_job_agent --setup
```

`--setup` installs the Python packages into a private virtual environment
in the engine folder (`.venv/`, nothing system-wide, works with Homebrew
Python) and the Node package, creates your agent home, and opens the input
forms in your browser. The forms are served from your own machine only
(127.0.0.1) and save straight into your agent home. Stop with Ctrl+C;
reopen later with `./run.sh --home ~/my_job_agent form`.

Keep the agent home outside this repository (or in `my_agent/`, the
default when `--home` is left out, which git ignores).

### 2. Set up the search (required)

In the **Search setup** tab, enter keywords and locations and click
**Save search setup**. Then check:

```
./run.sh --home ~/my_job_agent status
./run.sh --home ~/my_job_agent plan
```

### 3. The agent home

The setup created blank inputs, empty state files, the `output/` folder,
an empty weekly page (`output/jobs-on-market.html`) and two empty intake
folders, `inputs/intake/cv/` and `inputs/intake/cl/`. Any command, or plain
`./run.sh`, fills in whatever is missing. Nothing existing is ever
overwritten.

### 4. Add candidate data (optional, any time)

Any of these, and you can combine them:

- **Form:** the **Candidate profile** tab, then **Save candidate profile**.
- **Existing documents, method 1:** `./run.sh --home ~/my_job_agent intake cv path/to/my_cv.pdf`
- **Existing documents, method 2:** copy them into `inputs/intake/cv/` and
  `inputs/intake/cl/`, then click **Update** in the third tab (or run
  `./run.sh intake scan`; every run also picks them up).

When a CV and the form disagree, the newest entry is used and the change
is listed for you to confirm:

```
./run.sh --home ~/my_job_agent intake conflicts
```

### 5. Run it

```
./run.sh --home ~/my_job_agent collect
./run.sh --home ~/my_job_agent weekly
```

or the whole pass at once, and then every morning automatically:

```
./run.sh --home ~/my_job_agent run weekly
./run.sh --home ~/my_job_agent schedule
```

`schedule` prints the cron line (or the macOS launchd file) to install.
Setting `JOB_AGENT_HOME=~/my_job_agent` saves typing `--home`.

Optionally, give an AI agent `AGENT_PROMPT.md` and the agent-home path, as
a scheduled task or in a chat ("run the weekly pass", "sync my decisions"),
for LinkedIn, Indeed and fully tailored documents.

### 6. Decide and review

Open the page in your normal browser with
`./run.sh --home ~/my_job_agent open` (it is `output/jobs-on-market.html`).
Accept or Reject each posting, then click **Sync decisions** (you pick the
`state` folder once). The next sync applies the decisions, and accepted
postings get documents in `output/CV/`, `output/CL/` and `output/JD/`.

### Try it first with fictional data

```
./run.sh demo
```

This builds a fictional agent home in `demo/home/` and runs every step.
Example output is in `demo/preview/`.

---

## Repository layout

```
run.sh                  the single entry point
engine/                 Python engine and the .docx renderer (Node)
engine/collect/         online collectors, matching rules, liveness checks
AGENT_PROMPT.md         instructions for the AI agent
skills/tailor-documents the CV / cover-letter procedure
forms/                  browser forms: search setup and candidate profile
inputs_templates/       blank inputs copied into a new agent home
state_templates/        empty tracker, notes, rejection log, decisions file
defaults/               engine defaults and employer presets
demo/                   fictional data and example output
docs/                   inputs, intake, commands, state files, document spec
tests/                  offline tests with recorded API responses
```

More detail: `docs/commands.md` (every command), `docs/inputs.md` (every
setting), `docs/intake.md` (candidate data), `docs/state_files.md` (the
tracker and the Accept/Reject loop), `docs/document_spec.md` (document
format).

## Privacy

This repository holds only generic code, templates and fictional demo
data. Your agent home (inputs, tracker, notes, decisions and generated
documents) stays wherever you put it and should never be committed to a
public repository.

## License and authorship

MIT License, see `LICENSE`. Copyright (c) 2026 manpmanp.

### Credits

Some methods follow two open-source projects. Both were reimplemented
here in Python after studying their code; no code was copied.

- [Dossier](https://github.com/AienTech/dossier) (AGPL-3.0): posting-page
  reading (JSON-LD JobPosting first, then the page's main text, with a
  minimum length that flags browser-built pages), robots.txt matching per
  RFC 9309, the JSearch, Adzuna and Hacker News sources, and the typed
  requirements and fit-score format of the optional AI review.
- [PixelRAG](https://github.com/StarTrail-org/PixelRAG) (Apache-2.0):
  rendering browser-built pages after the load event and a quiet network
  before reading them, and treating text read from a page as untrusted.


Designed and directed by manpmanp. Code and documentation were
generated with Claude (Anthropic) under his direction and review.
