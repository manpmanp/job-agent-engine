<!--
  Job-search agent engine
  File:    docs/commands.md
  Purpose: Reference of every ./run.sh command.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.3.0
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
| `--setup` (or `setup`) | Installs the dependencies the first time (Python into `.venv/` in the engine folder, nothing system-wide; Node into `node_modules/`), creates the agent home, then opens the input forms in your browser. |
| `form [--port N] [--no-browser]` | Opens the input forms without the install step. Served locally (127.0.0.1 only), so Save writes straight into the agent home and Update imports documents from the intake folders. Stop with Ctrl+C. |
| `test` | Runs the offline test suite. |
| `init` | Creates a new agent home with blank inputs and empty state files, and lists what it created. Every other command does the same silently when something is missing (including `output/` and the weekly page). Never overwrites existing files. |
| `status` | Lists every feature as on or off, why, and what would switch it on. |
| `plan` | Prints the search plan from the search config, employer list and rejection history. |
| `collect [--only jobtech\|employers]` | Fetches postings online (Arbetsformedlingen API, employer job boards and careers pages), filters, classifies and adds new ones to the tracker. |
| `verify` | Checks that tracked postings are still open; closed ones become Expired (accepted ones only get a note). |
| `enrich` | Optional AI review of collected postings through your Anthropic API key. |
| `run weekly\|daily\|auto` | A complete run without an agent. `weekly`: collect, verify, sync, enrich, templates, page and summary. `daily`: sync, templates, page. `auto`: weekly on your search day, daily otherwise. |
| `schedule` | Prints the cron line and the macOS launchd file to run `run auto` every morning. |
| `add-postings <file.json>` | Merges found or updated posting rows into the tracker. |
| `weekly ["note"]` | Writes the weekly page (`output/jobs-on-market.html`) and the weekly summary. |
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
| `tailor check <spec.json>` | Mechanical checks on a document spec. |
| `tailor render <spec.json> --posting "<URL>\|\|<Title>"` | Checks and renders a spec to the posting's file name. `--overwrite`, `--force` available. |
| `tailor jd "<URL>\|\|<Title>" [--text <file>]` | Job-description snapshot (PDF when a converter is available, HTML otherwise). |
| `tailor done "<URL>\|\|<Title>"` | Marks the posting's documents as drafted. |
| `checkpoint phase <date> <phase> <status> [note]` | Records search progress. |
| `checkpoint employer <date> "<name>" <found> [note]` | Records that a named employer was checked. |
| `checkpoint report [date]` | Coverage report against the employer list. |
| `note "<text>"` | Appends to the notes file. |
| `demo` | Builds a fictional agent home and runs every step on it. |
