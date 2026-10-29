<!--
  Job-search agent engine
  File:    engine/defaults/employer_presets/README.md
  Purpose: How to add a reusable employer preset.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.3.0
  Date:    2026-10-28
-->

# Employer presets

A preset is a reusable list of employers, for example all hardware
companies in one region. Put it here as `<name>.json` and name it in
`search_config.json` under `employer_presets`. Your own
`inputs/employers.json` can extend, override or exclude entries.

```json
{
  "preset": "<name>",
  "description": "What this list covers.",
  "employers": [
    {"name": "Example Corp", "urls": ["https://boards.greenhouse.io/examplecorp"]},
    {"name": "Another AB", "urls": ["https://www.another.example/careers"], "note": "optional"}
  ]
}
```

Careers URLs on Greenhouse, Lever, Ashby, Workday or SmartRecruiters are
read through their job-board APIs; other URLs as ordinary pages.
