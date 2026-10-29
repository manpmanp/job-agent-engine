<!--
  Job-search agent engine
  File:    cloud/README.md
  Purpose: The online search on your own Cloudflare account: what it does, how to deploy it, how it connects to your computer.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.4.0
  Date:    2026-10-29
-->

# Online search (optional)

Runs the job search every day on **your own** Cloudflare account (free
plan), so new postings are waiting even when your computer is off, and
you can Accept or Reject from your phone. Your CV, cover letters and
documents never come here: the Job Agent app on your computer fetches the
postings and your decisions and makes the documents locally.

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/manpmanp/job-agent-engine/tree/main/cloud)

## What is online, what stays on your computer

| Online (your Cloudflare account) | Only on your computer |
|---|---|
| Search keywords, places, employer list | CV, cover letters, profile |
| Postings found, with their descriptions | Characteristics, tailoring rules, references |
| Accept / Reject decisions | Generated CVs, letters, JD snapshots |
| Optional JSearch / Adzuna keys | Optional Anthropic API key |

The online page is protected by the password you choose. Nobody else's
data is on your account, and nothing goes to the author of this project.

## Deploy (about 5 minutes)

1. Click **Deploy to Cloudflare** above and sign in (or create a free
   Cloudflare account).
2. When asked, fill in:
   - **APP_PASSWORD**: the password for your online page. Choose a long one.
   - **SYNC_TOKEN**: a long random text; your computer uses it to fetch
     your postings. A password manager can generate one.
   - JSearch / Adzuna: optional; leave them as they are to skip.
3. Deploy. Cloudflare creates the Worker and its database. Open the
   address it shows (`https://job-agent.<your-name>.workers.dev`), log in,
   and fill in **Setup** (what to search for, where, which employers).

The search then runs every day after 06:00 UTC (change `RUN_HOUR_UTC` in
the Worker's settings), and on your search day it also checks that
tracked postings are still open. **Search now** on Home starts one at any
time.

**Extra protection (recommended):** in the Cloudflare dashboard, put the
Worker behind **Cloudflare Access** (Zero Trust > Access > Applications,
free for up to 50 users) so only your e-mail address can reach the page.
Leave the path `/api/sync/*` outside Access (bypass), because your
computer uses it with the sync token.

## Connect your computer

In the Job Agent app on your computer: **Settings > Online search**,
enter the address and the sync token, then **Save and fetch now**. From
then on:

- every run of the app (and the daily run) fetches new postings,
  descriptions and decisions, and sends back decisions you made on the
  computer (the newer decision wins);
- **Search now** on the computer starts the online search and fetches;
- the computer no longer searches by itself (set
  `search_config.cloud.local_collect: true` to search in both places);
- postings that get documents on the computer show "Documents made on
  your computer" online.

From the terminal: `./run.sh cloud connect <address> <token>`,
`./run.sh cloud pull`, `./run.sh cloud search`, `./run.sh cloud status`.

## Limits of the free plan, and how the search copes

A Worker run on the free plan may use 10 ms of CPU and 50 outgoing
requests. A search is therefore split into small steps kept in the
database (one keyword page, one employer board, one posting page each).
A timer works through them every 2 minutes; while the page is open, it
also works on them as it updates. A normal daily search finishes within
an hour. Steps that hit a limit are retried, at most three times. If you
watch many large employers and see "exceeded CPU" errors in the Worker's
logs, the Workers Paid plan ($5/month) raises the limits; nothing else
changes.

What the online search does not do: render pages that are built in the
browser (the app on your computer can, with **Add a posting**), read
LinkedIn or Indeed directly (use JSearch, or an AI agent), or write
documents.

## Develop

```
cd cloud
npm install
cp .dev.vars.example .dev.vars      # set a password and token
npm run dev                         # local Worker with a local database
npm test                            # shared rule tests + end-to-end Worker tests
npm run sync                        # after changing app/, forms/ or defaults/
```

Manual deploy without the button: `npx wrangler d1 create job-agent`
(put the `database_id` it prints into `wrangler.jsonc`), then
`npx wrangler secret put APP_PASSWORD`, `npx wrangler secret put SYNC_TOKEN`
and `npm run deploy`.

The matching rules are a TypeScript port of `engine/collect/match.py`;
`tests/shared/match_cases.json` is run by both test suites so the two stay
the same.
