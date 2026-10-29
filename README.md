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

A job-search app that runs on your own computer. It searches for job
postings that match your keywords and places, keeps every posting in a
tracker spreadsheet, lets you Accept or Reject each one, and drafts a CV,
cover letter and job-description snapshot for every posting you accept.
It never applies, sends or posts anything on your behalf.

The engine contains no personal data. Everything about you lives in your
own **agent home** folder and is read at run time. To start you only need
search keywords and locations. Everything else is optional and can be
added whenever you like.

---

## Get started

Pick your computer. Each package has everything it needs: no Python or
other software to install. Downloads are on the
[Releases page](https://github.com/manpmanp/job-agent-engine/releases/latest).

### Mac

1. Download **JobAgent-macOS.dmg** and open it.
2. Drag **Job Agent** onto **Applications**.
3. Open **Job Agent** from Applications. The first time, macOS says it
   cannot check the app (it is not signed by Apple yet): click **Done**,
   then **System Settings > Privacy & Security > Open Anyway**. Only once.

### Windows

1. Download **JobAgent-Windows-Setup.exe** and run it. If Windows says
   "Windows protected your PC", click **More info > Run anyway** (the app
   is not signed by Microsoft yet). No administrator rights are needed.
2. Start **Job Agent** from the Start menu.

### Linux

1. Download **JobAgent-Linux.tar.gz**, then:

   ```
   tar xzf JobAgent-Linux.tar.gz
   cd JobAgent-Linux
   ./install.sh
   ```

2. Start **Job Agent** from your applications menu (or run `job-agent`).

### Then, on any computer

Job Agent opens in your web browser. It runs only on your computer and
keeps your job search in a **JobAgent** folder in your home folder.

1. **Setup:** type what to search for (job titles or skills) and where
   (towns, regions or countries). Optionally drop in your CV, and list
   employers you want watched.
2. **Home > Search now.** New postings appear under **Postings**.
3. **Postings:** **Accept** the ones you want; **Reject** the others with a
   reason (future searches learn from it).
4. **Documents:** for each accepted posting, make a **template** (your
   details plus the posting's keywords, experience left as placeholders),
   or, if you added your CV, a **tailored draft**:
   - **Copy for Claude** copies everything to your clipboard. Paste it
     into any Claude chat, then paste the answer back with **Paste
     Claude's answer**. No key needed.
   - **Write with AI** does the same in one click, with your own
     Anthropic API key (Settings).

   Drafts are Word files in your folder. Nothing is ever sent or applied
   for you.
5. **Settings > Run every morning:** the search then runs by itself
   every day, even when the app is closed.

**Add a posting** reads any job link you found yourself and adds it.
Close the app with **Settings > Quit the app**.

### Running it from the code instead

For developers, or if you prefer not to use the packages: install
Python 3.9 or newer, download this repository (**Code > Download ZIP**,
or `git clone`), and follow the short README in the folder for your
computer: [`launchers/macos`](launchers/macos/README.md),
[`launchers/windows`](launchers/windows/README.md) or
[`launchers/linux`](launchers/linux/README.md).

### Online search (optional)

The search can also run every day on your own free Cloudflare account,
so new postings are waiting even when your computer is off and you can
decide from your phone. Your CV and documents stay on your computer; the
app fetches the postings and decisions from there. See
[`cloud/README.md`](cloud/README.md):

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/manpmanp/job-agent-engine/tree/main/cloud)

### Try it first with fictional data

```
./run.sh demo
```

builds a fictional job search in `docs/demo/home/`; open it with
`./run.sh --home docs/demo/home app`. Example documents are in `docs/demo/preview/`.

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
 |  verify    re-check that postings are open|        |  agent/AGENT_PROMPT.md:    |
 |  sync      apply your Accept/Reject       |  --->  |  LinkedIn / Indeed, judges |
 |  weekly    weekly page + summary          |        |  unclear postings, writes  |
 |  tailor    CV / CL (template or full)     |        |  fully tailored CV / CL    |
 |  enrich    optional AI review via API key |        +---------------------------+
 +-------------------------------------------+
                  |  reads / writes
                  v
 +-------------------------------------------+        +---------------------------+
 |  Your agent home (private, on your disk)  | <----  |  You, in the app: setup,   |
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
- **Shows every posting in the app** (and on a static weekly page),
  applies your Accept/Reject decisions, and writes template documents for
  accepted postings.
- **Optional AI review** (`./run.sh enrich`) with your own Anthropic API
  key, to refine category, seniority and fit notes.
- **One command for a whole run**: `./run.sh run auto` does the full weekly
  pass on your search day and a sync on other days. The app's
  **Run every morning** switch (or `./run.sh schedule install`) runs it
  daily: launchd on a Mac, cron on Linux, Task Scheduler on Windows.

Every source is called politely: the engine names itself, waits between
requests to the same site, respects robots.txt (RFC 9309) for ordinary
pages, fetches pages only from public addresses, and only uses public job
data. Text read from pages is treated as data, never as instructions.
A source that fails is reported and skipped; the run always finishes.

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
| Any time | you | open the app, Accept or Reject postings, make documents |
| Any time | you | add or change your CV or profile on the app's Setup page |

---

## What you get at each level of input

| You provide | You get |
|---|---|
| Keywords + locations | Online collection from Arbetsformedlingen, posting tracker, the app's posting list and a weekly summary, Accept/Reject, **template** CV/CL for accepted postings (structure and prompts built from the posting's keywords; nothing invented, no name needed) |
| + employer list or preset | Collection from each employer's job board or careers page, with a coverage report every run |
| + Anthropic API key (optional) | AI review of each collected posting |
| + profile (form) or an existing CV/CL | Fit notes on new postings, **tailored** CV/CL built only from your own material |
| + personal characteristics | Cover-letter motivation based on how you actually work |
| + personal tailoring rules / checks | Your mandatory entries and style rules, checked automatically |
| + document style | Your fonts and colours |

`./run.sh status` lists every feature as on or off, why, and what would
switch it on. A missing optional input is never an error.

---

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

Optionally, give an AI agent `agent/AGENT_PROMPT.md` and the agent-home path,
as a scheduled task or in a chat ("run the weekly pass", "sync my
decisions"), for LinkedIn, Indeed and fully tailored documents.

The static weekly page (`output/jobs-on-market.html`, `./run.sh open`)
still works without the app: Accept or Reject there, click **Sync
decisions** (pick the `state` folder once), then `./run.sh sync`.

---

## Repository layout

```
README.md, LICENSE
run.sh                  terminal entry point
requirements.txt        Python packages (installed into .venv/ automatically)
launchers/              everything to start Job Agent, per system:
  <system>/             double-click launcher and its README (run from the code)
  <system>/package/     what goes into that system's download (instructions, installer script)
  start.py              what the launchers and the packaged apps run
  job_agent.spec        build recipe for the packaged apps
engine/                 the program
  collect/              online collectors, matching rules, posting reader, liveness checks
  web/                  the app page and the input form
  defaults/             engine defaults, skill vocabulary, employer presets
  templates/            blank inputs and empty state files for a new agent home
agent/                  instructions and the CV / cover-letter procedure for an optional AI agent
cloud/                  the optional online search (Cloudflare Worker + D1)
docs/                   reference documentation; docs/demo/ has fictional data and example output
tests/                  offline tests with recorded responses; tests/shared/ is run by the Worker too
.github/workflows/      tests, and the builds of the three packages
```

More detail: `docs/commands.md` (every command), `docs/inputs.md` (every
setting), `docs/intake.md` (candidate data), `docs/state_files.md` (the
tracker and the Accept/Reject loop), `docs/document_spec.md` (document
format), `docs/job_sites.md` (job sites by country, with sources).

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
