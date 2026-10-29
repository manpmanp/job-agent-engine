<!--
  Job-search agent engine
  File:    docs/commands.md
  Purpose: Reference of every ./run.sh command.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.4.0
  Date:    2026-10-28
-->

# Commands

All commands go through the runner. The agent home is given with `--home`
before the command, or with the `JOB_AGENT_HOME` environment variable
(default: `my_agent/` inside the engine folder, which is git-ignored).

```
./run.sh --home <AGENT_HOME> <command> [arguments]
```

| Command | What it does |
|---|---|
| *(none)* | `./run.sh` on its own creates the agent home if needed and does today's run (`run auto`). |
| `--setup` (or `setup`) | Installs the Python packages into `.venv/` in the engine folder (nothing system-wide; `run.sh` also does this by itself whenever they are missing), creates the agent home, and opens the app on its Setup page. Add `--browser` to also install Playwright's headless Chromium (about 100 MB, once) for posting pages built in the browser, `--remove-browser` to remove it. |
| `form [--port N] [--no-browser]` | Opens the app on its Setup page (search setup and profile). |
| `test` | Runs the offline test suite. |
| `clean` | Removes what the engine no longer uses or rebuilds on demand: Node modules from versions before 0.4, Python caches, Finder's `.DS_Store` files, and folders left empty after the 0.4.2 reorganisation. Never touches `.venv` or any agent home. |
| `release` | For maintainers: updates this folder from GitHub, then tags the version in `engine/__init__.py` on the newest commit and pushes it, so GitHub builds and attaches the three packages. If that tag already sits on an older commit, it asks before moving it. |
| `init` | Creates a new agent home with blank inputs and empty state files, and lists what it created. Every other command does the same silently when something is missing (including `output/` and the weekly page). Never overwrites existing files. |
| `status` | Lists every feature as on or off, why, and what would switch it on. |
| `plan` | Prints the search plan from the search config, employer list and rejection history. |
| `collect [--only jobtech\|employers\|aggregators\|jsearch\|adzuna\|hn]` | Fetches postings online (Arbetsformedlingen API, employer job boards and careers pages, and any optional aggregators you switched on), opens link leads to read the posting, filters, classifies and adds new ones to the tracker. |
| `fetch <url> [--add] [--employer E] [--title T] [--no-render]` | Reads one posting page: structured JobPosting data, else the page's main text, else a headless-browser render for pages built in the browser. Prints what it found, saves the text for tailoring and the JD snapshot, and with `--add` puts it in the tracker even if it is outside your filters. |
| `verify` | Checks that tracked postings are still open; closed ones become Expired (accepted ones only get a note). |
| `enrich` | Optional AI review of collected postings through your Anthropic API key. |
| `run weekly\|daily\|auto` | A complete run without an agent. `weekly`: collect, verify, sync, enrich, templates, page and summary. `daily`: sync, templates, page. `auto`: weekly on your search day, daily otherwise. |
| `schedule [install\|remove\|status]` | Installs or removes the daily run at 08:02 (launchd on macOS, cron on Linux, Task Scheduler on Windows), or shows it. Without an argument it prints what would be installed. The app's Settings has the same switch. |
| `cloud [pull\|connect <address> <token>\|disconnect\|search\|status]` | Your online search (`cloud/`): `pull` fetches new postings, descriptions and decisions and sends back decisions made here (also done by every run); `connect` saves the address and sync token and fetches; `search` starts a search online. |
| `app [--port N] [--no-browser]` | Opens the local app in your browser (127.0.0.1 only). Plain `./run.sh` in a terminal does the same. If it is already running, the browser is pointed at it. |
| `add-postings <file.json>` | Merges found or updated posting rows into the tracker. |
| `weekly ["note"]` | Writes the static weekly page (`output/jobs-on-market.html`, for use without the app) and the weekly summary. |
| `open` | Opens the weekly page from the local file in your default browser (builds it first if missing). |
| `sync [file]` | Applies new or changed Accept/Reject decisions, then refreshes the page. |
| `intake cv\|cl <file>` | Stores a prepared CV or cover letter and extracts its text. |
| `intake scan` | Imports every new document copied into `inputs/intake/cv/` and `inputs/intake/cl/` (same as the form's Update button; every run does it too). |
| `intake form <file>` | Submits a filled profile form. |
| `intake fragment <file> --from <id>` | Submits a profile fragment extracted from an uploaded document. |
| `intake set <field> <value>` | Sets one field, for example `identity.name`. |
| `intake conflicts` / `intake resolve <n> keep-new\|keep-previous` | Shows and settles conflicts between sources. |
| `intake sources` / `intake rebuild` | Lists all submissions / rebuilds the profile. |
| `tailor pending` | Accepted postings without documents, with their keys and the current mode. |
| `tailor template "<URL>\|\|<Title>"` or `--all-pending` | Template CV and CL for a hypothetical candidate. |
| `tailor conventions "<URL>\|\|<Title>"` | How this posting's documents are written: market (from its country), sector (industry or academia), level, page size, length, details to leave out, salutation and closing. |
| `tailor check <spec.json>` | Mechanical checks on a document spec. `--posting "<URL>\|\|<Title>"` adds that market's checks. |
| `tailor render <spec.json> --posting "<URL>\|\|<Title>"` | Checks and renders a spec to the posting's file name. `--overwrite`, `--force` available. |
| `tailor jd "<URL>\|\|<Title>" [--text <file>]` | Job-description snapshot (PDF when a converter is available, HTML otherwise). |
| `tailor done "<URL>\|\|<Title>"` | Marks the posting's documents as drafted. |
| `checkpoint phase <date> <phase> <status> [note]` | Records search progress. |
| `checkpoint employer <date> "<name>" <found> [note]` | Records that a named employer was checked. |
| `checkpoint report [date]` | Coverage report against the employer list. |
| `note "<text>"` | Appends to the notes file. |
| `demo` | Builds a fictional agent home and runs every step on it. |
