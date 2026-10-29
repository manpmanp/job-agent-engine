<!--
  Job-search agent engine
  File:    docs/state_files.md
  Purpose: The tracker, logs and the Accept/Reject loop.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.3.0
  Date:    2026-10-28
-->

# State files

The engine creates these in `state/` (or wherever `agent_home.json` points)
the first time they are needed, from the empty versions in
`engine/templates/state/`. They are your job-search history: keep them private.

| File | Written by | Purpose |
|---|---|---|
| `Job_Search_Tracker.xlsx` | engine (`add-postings`, `sync`, `tailor done`) | The complete record of every posting. Never edit rows by hand. |
| `Job_Search_Notes.txt` | agent (`note`) | Running log of what each run did and learned. |
| `rejection_patterns.csv` | engine (`sync`) | One line per rejection reason; soft context for later searches. |
| `decisions_sync.json` | the app (Accept/Reject), or the static weekly page ("Sync decisions") | Your Accept/Reject decisions. The app applies them at once; from the static page they are applied by `./run.sh sync` or the next run. |
| `.agent_home_id` | engine | Random ID of this agent home. The weekly page keeps its browser storage under it and only syncs into the folder that holds it, so two agent homes never mix decisions. |
| `new_postings/` | agent | The JSON rows each search found, kept as a record. |
| `sync_logs/` | engine | One audit file per sync plus `latest_state.json` for diffing. |
| `search_progress/` | engine (`checkpoint`) | Per-run phase and employer checkpoints. |
| `network_log.jsonl` | engine (every request) | One line per request to the internet: time, purpose, address (key-like values hidden), what was sent, bytes out and in, status. Shown in the app under Settings > Network activity. Header values, where API keys travel, are never recorded. Trimmed to the newest 3000 lines past 2 MB. |
| `all_listings.json` | engine (`collect`) | Every job the last search saw that did not become a posting, with why (`none of your keywords`, `outside your places`, `excluded word: ...`). Shown in the app under Postings > Not matched, where one click adds it. |
| `document_choices.json` | the app (Documents tab), `tailor choose` | The position type or market you chose for single postings. |

`backups/<date_time>/` in the agent home (not in `state/`) holds what
Settings > Start over (or `./run.sh reset`) moved aside, in its original
place in the folder. Move files back from there to undo a reset.

## The tracker

Four sheets:

- **Active Advertisements**: everything not expired or rejected, newest
  first. Columns A to H (Action, Employer, Title, Seniority Level,
  Location, Remote/Hybrid/Onsite, Announce Date, Days Since Posting) are
  always visible; the rest are grouped and collapsed (click **[+]** above
  column I). *Action* flags a fixed deadline within a day, or a rolling
  posting older than `act_asap_after_days` without a decision. Seniority is
  colour-coded from your seniority policy.
- **Rejected Advertisements**: Status starts with `Rejected:` followed by
  the reasons.
- **Expired Advertisements**: Status `Expired`.
- **Legend**: the seniority colours.

Rows are identified by (URL, Title), not URL alone, because some employers
use one careers URL for several postings. Rows are moved between sheets,
never deleted. Updates are idempotent.

Status values: `New`, `Approved - ready for tailored documents`,
`Rejected: <reasons>`, `Expired`, or anything else the agent records
(for example `Unverified`).

## The Accept/Reject loop

1. `./run.sh weekly` writes the page. Open it in your normal browser
   (double-click the file).
2. **Accept** means "draft documents for this one". **Reject** asks for one
   or more reasons. Decisions are kept in that browser and survive the page
   being regenerated.
3. **Sync decisions** writes `decisions_sync.json` into the state folder
   (you pick the folder once; later clicks are silent). Browsers without
   folder access download the file instead; move it into the state folder.
4. `./run.sh sync`, or the agent's next run, applies only what is new or
   changed. Syncing twice is harmless.
5. Accepted postings appear in `./run.sh tailor pending`.

The page lives on your own disk and cannot notify the agent. Decisions
reach the tracker only when a sync runs.
