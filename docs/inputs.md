<!--
  Job-search agent engine
  File:    docs/inputs.md
  Purpose: Reference of every input file and setting in an agent home.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.4.0
  Date:    2026-10-28
-->

# Inputs

All inputs live in your agent home under `inputs/`. `./run.sh init`
creates blank versions. Keys beginning with `_` are help text and ignored.

## Required for searching: `inputs/search_config.json`

| Key | Required | Meaning |
|---|---|---|
| `keywords` | yes | Search terms. Each query combines one keyword with one location. Specific terms work better than broad ones. |
| `locations` | yes | Strings or objects `{"name", "country", "aliases": [...], "priority"}`, in priority order. Matching ignores accents (Vasteras = Västerås); use `aliases` for other spellings and nearby towns (Bærum for Oslo). `country` (SE, DK, ...) lets remote postings in that country through. |
| `weekly_list` | no | `enabled` (default true), `full_search_day` (default Monday), `summary_markdown` (default true). |
| `roles_description` | no | The kind of roles you want, in plain words. |
| `categories` | no | Exactly one is assigned per posting. Defaults in `engine/defaults/search_defaults.json`. |
| `seniority` | no | `preferred`, `flag_as_too_senior`, `flag_as_too_junior`. Flagged postings are kept and colour-coded, never discarded. |
| `work_arrangement` | no | `remote_ok`, `hybrid_ok`, `onsite_ok`. |
| `max_commute` | no | Free text, for example `1.5h one-way`. |
| `sources` | no | Built into the engine: `jobtech` (Arbetsformedlingen API), `employer_sites` (job boards and careers pages of named employers), `confirm_leads` (default true: links found on careers pages are opened and the posting is read, at most `confirm_leads_max`, default 25, per run). Optional aggregators, off by default: `jsearch` (Google for Jobs: LinkedIn, Indeed and company sites, most countries; key `jsearch_api_key`, optional `jsearch_host` `openwebninja` or `rapidapi`; `jsearch_pages` pages per query, each one request of your plan), `adzuna` (19 countries, not Sweden or Denmark; `adzuna_app_id`, `adzuna_app_key`; descriptions are shortened by the source), `hn_who_is_hiring` and `yc_jobs` (Hacker News, no key). Aggregators use each location's `country`. Used by the AI agent: `indeed`, `linkedin_read_only`, `web_search`, `named_employers`, `extra_sites`. |
| `match_scope` | no | `title` (default: a keyword must be in the posting title) or `title_or_description` (also accept postings whose description contains the keyword as a phrase; finds more, but also software or other roles that only mention the term). |
| `exclude_terms` | no | Titles containing any of these are skipped (for example `sales`, `säljare`). |
| `skill_terms` | no | Extra terms to pick out for the skills summary (search keywords and profile skills are always used). |
| `category_rules` | no | `{"<category>": ["term", ...]}`: first rule whose term appears in title or description sets the category. |
| `enrichment` | no | Optional AI review: `enabled`, `model` (default `claude-haiku-5-5`), `send_profile` (default false: the profile is not sent), `max_per_run`. Needs `ANTHROPIC_API_KEY` or `inputs/secrets.json` `{"anthropic_api_key": "..."}`. |
| `job_sites` | no | Set in the app under Setup > Countries and job sites: `countries` (ISO codes, for example `["SE", "DK"]`; default: the countries of your locations), `skip` (addresses of listed sites you do not want), `custom` (your own sites, `{"name", "url"}`). The catalogue is `engine/defaults/job_sites.json` (readable: `docs/job_sites.md`); sites without a built-in search are for you or your agent to read. |
| `credible_sources` | no | Sources that count as confirmation that a posting is live. |
| `employer_presets` | no | Names of files in `engine/defaults/employer_presets/`. |
| `rejection_reasons` | no | The checkbox list on the weekly page. |
| `document_market` | no | The writing conventions used when a posting's country cannot be detected (for example "Remote"); default `international`. Otherwise each posting gets its own country's conventions (`engine/defaults/document_conventions.json`). |
| `calendar` | no | `enabled`, `calendar_id`. Events go only to this calendar. |
| `git` | no | `commit_state`, `push`, if your agent home is a git repo. |
| `page_title` | no | Title of the weekly page. |
| `stale_after_days`, `act_asap_after_days` | no | Thresholds for the stale and act-soon flags. |

A blank value keeps the default.

## Optional inputs

| File | Used for |
|---|---|
| `inputs/employers.json` | Your named employers: `{"name", "urls": [...]}`. Careers URLs on Greenhouse, Lever, Ashby, Workday or SmartRecruiters are read through their job-board APIs automatically; other URLs as pages; `indeed:` / LinkedIn entries are left to the agent. An entry can force a source with `"ats": {"type": "greenhouse", "board": "..."}` (or `lever`/`company`, `ashby`/`org`, `workday`/`host`,`tenant`,`site`, `smartrecruiters`/`company`). `mode: "extend"` adds to the presets (same name replaces the preset entry); `"override"` uses only yours; `exclude` removes names. |
| `inputs/secrets.json` | Optional keys: `anthropic_api_key` (`enrich`), `jsearch_api_key`, `jsearch_host`, `adzuna_app_id`, `adzuna_app_key`. Environment variables `ANTHROPIC_API_KEY`, `JSEARCH_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` work too. Keep it private; never commit it. |
| `inputs/candidate/` | Your profile and uploaded documents. Managed with `./run.sh intake`; see `intake.md`. |
| `inputs/intake/cv/`, `inputs/intake/cl/` | Drop folders for existing CVs and cover letters, imported by the form's Update button, `./run.sh intake scan` and every run. |
| `inputs/characteristics.md` | How you work, with real examples. Only shapes cover-letter motivation; never quoted. |
| `inputs/tailoring_rules.md` | Your own mandatory rules for documents (entries that must always appear, exact wording for specific projects, style corrections). |
| `inputs/tailoring_checks.json` | Mechanical checks: `cv_must_contain`, `cl_must_contain`, `must_not_contain`. `tailor render` refuses a spec that fails them. |
| `inputs/references/` | Any authoritative files the agent should consult (a publication list, a detailed technical profile). |
| `inputs/document_style.json` | `font`, `banner_color`, `accent_color`, `secondary_text_color`, `body_text_color`, `page_size` (A4/Letter), `avoid_em_dash`, `cl_closing`. Leave `page_size` and `cl_closing` out to follow each posting's market (Letter and "Sincerely," for the US, A4 and "Kind regards," for Sweden). |
| `inputs/document_conventions.json` | Your changes to the writing conventions, in the same shape as `engine/defaults/document_conventions.json`: `markets` (countries) and `types` (the ten position types). The app's Settings > Writing style writes `types` for you (sections in order with heading, length and focus; confidence 1 to 5; emphasis; wording; CV and letter length; letter focus). Only what you write replaces the default, for example `{"markets": {"us": {"letter": {"closing": "Best regards,"}}}}`. |
| `state/document_choices.json` | The position type or market you chose for single postings in the Documents tab (or with `tailor choose`). |

## Using an existing folder layout: `agent_home.json`

Every path can be remapped, so an agent home that predates the engine can
be used without moving files. Put `agent_home.json` in the agent-home root:

```json
{
  "paths": {
    "tracker": "Job_Search_Tracker.xlsx",
    "notes": "Job_Search_Notes.txt",
    "rejection_log": "rejection_patterns.csv",
    "decisions": "decisions_sync.json",
    "weekly_html": "weekly-job-search.html",
    "sync_logs": "output_files_gitignore/sync_logs",
    "search_progress": "output_files_gitignore/search_progress",
    "cv_out": "output_files_gitignore/CV",
    "cl_out": "output_files_gitignore/CL",
    "jd_out": "output_files_gitignore/JD"
  }
}
```

Keys: `search_config`, `employers`, `document_style`, `tailoring_rules`,
`tailoring_checks`, `characteristics`, `references`, `candidate`,
`tracker`, `notes`, `rejection_log`, `decisions`, `new_postings`,
`sync_logs`, `search_progress`, `weekly_html`, `weekly_summary`, `specs`,
`cv_out`, `cl_out`, `jd_out`. Anything not listed keeps its default.
