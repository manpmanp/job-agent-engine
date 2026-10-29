// Job-search agent engine, online search
// File:    cloud/scripts/sync-shared.mjs
// Purpose: Copies the files the Worker shares with the local engine (app page, form, defaults) into cloud/src/shared/.
//          The Deploy to Cloudflare build only sees the cloud/ folder, so the copies are committed; a test checks they are current.
// Author:  manpmanp <manp.node@gmail.com>. Generated with Claude (Anthropic). MIT.
import { copyFileSync, mkdirSync } from "node:fs";
const root = new URL("../../", import.meta.url), out = new URL("../src/shared/", import.meta.url);
mkdirSync(out, { recursive: true });
for (const [from, to] of [["engine/web/app.html", "index.html"], ["engine/web/form.html", "candidate_form.html"],
                          ["engine/defaults/search_defaults.json", "search_defaults.json"], ["engine/defaults/skill_vocabulary.json", "skill_vocabulary.json"],
                          ["engine/defaults/job_sites.json", "job_sites.json"]]) {
  copyFileSync(new URL(from, root), new URL(to, out));
  console.log(`copied ${from}`);
}
