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

## Get started (no terminal needed)

### 1. Get it

Pick one:

- **Ready-made app** (nothing else to install): download the file for
  your computer from the [Releases page](https://github.com/manpmanp/job-agent-engine/releases):
  `JobAgent-macOS.zip`, `JobAgent-Windows.zip` or `JobAgent-Linux.zip`,
  and unzip it.
- **From the code**: on the repository page click **Code > Download ZIP**
  and unzip it (or `git clone` it). This needs Python 3.9 or newer
  ([python.org](https://www.python.org/downloads/); on Windows tick
  "Add python.exe to PATH").

### 2. Open it

Double-click:

| Computer | Ready-made app | From the code |
|---|---|---|
| Mac | **Job Agent** | **Job Agent.command** |
| Windows | **JobAgent.exe** | **Job Agent.bat** |
| Linux | **JobAgent** | **job-agent.sh** |

The app opens in your web browser. It runs only on your own computer
(nothing is put online) and keeps your job search in a **JobAgent**
folder in your home folder.

The first start from the code takes about a minute while it prepares
itself. The ready-made apps are not signed by Apple or Microsoft yet, so
the first time: on a Mac, right-click the app and choose **Open**; on
Windows, click **More info > Run anyway**.

### 3. Use it

1. **Setup:** type what to search for (job titles or skills) and where
   (towns, regions or countries). Optionally drop in your CV.
2. **Home > Search now.** New postings appear under **Postings**.
3. **Postings:** **Accept** the ones you want; **Reject** the others with a
   reason (future searches learn from it).
4. **Documents:** for each accepted posting, make a **template** (your
   details plus the posting's keywords, experience left as placeholders),
   or, if you added your CV, a **tailored draft**:
   - **Copy for Claude**: copies everything to your clipboard. Paste it
     into any Claude chat, then paste the answer back with **Paste
     Claude's answer**. No key needed.
   - **Write with AI**: does the same in one click, with your own
     Anthropic API key (Settings).
   Drafts are Word files in your folder. Nothing is ever sent or applied
   for you.
5. **Settings > Run every morning:** the search then runs by itself
   every day, even when the app is closed.

**Add a posting** reads any job link you found yourself and adds it.

Close the app with **Settings > Quit the app** (or close its window).

### Try it first with fictional data

```
./run.sh demo
```

builds a fictional job search in `demo/home/`; open it with
`./run.sh --home demo/home app`. Example documents are in `demo/preview/`.

## Using the terminal (optional)

Everything the app does is also a command, for scripting and for AI agents:

```
git clone https://github.com/manpmanp/job-agent-engine.git
cd job-agent-engine
./run.sh --home ~/my_job_agent app        # the app (also: plain ./run.sh)
./run.sh --home ~/my_job_agent status     # what is on and off, and why
./run.sh --home ~/my_job_agent run weekly # collect, verify, sync, page
./run.sh --home ~/my_job_agent fetch <url> --add
./run.sh --home ~/my_job_agent schedule install
```

`run.sh` installs its Python packages into a private `.venv/` in the
engine folder the first time (nothing system-wide; works with Homebrew
Python) and again whenever `requirements.txt` changes. Setting
`JOB_AGENT_HOME=~/my_job_agent` saves typing `--home`. Every command is in
`docs/commands.md`.

Candidate data can also come from files: `./run.sh intake cv my_cv.pdf`,
or by copying them into `inputs/intake/cv/` and `inputs/intake/cl/` (every
run picks them up). When sources disagree, the newest wins and the change
is listed for you to confirm (`intake conflicts`, or on the app's Home).

Optionally, give an AI agent `AGENT_PROMPT.md` and the agent-home path,
as a scheduled task or in a chat ("run the weekly pass", "sync my
decisions"), for LinkedIn, Indeed and fully tailored documents.

The static weekly page (`output/jobs-on-market.html`, `./run.sh open`)
still works without the app: Accept or Reject there, click **Sync
decisions** (pick the `state` folder once), then `./run.sh sync`.

---

## Repository layout

```
start.py, Job Agent.*    double-click launchers (macOS, Windows, Linux)
run.sh                  terminal entry point
app/                    the local app (one web page)
engine/                 Python engine, the app server and the .docx renderer
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
packaging/, .github/    builds of the ready-made apps
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
