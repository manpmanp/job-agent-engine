// Job-search agent engine, online search
// File:    cloud/src/pipeline.ts
// Purpose: Search runs as small queued tasks in D1: planning, claiming, filtering (port of engine/collect/__init__.py), storing, verifying.
// Author:  manpmanp <manp.node@gmail.com>
// Generated with Claude (Anthropic), under the author's direction and review.
// License: MIT (see LICENSE)
// Version: 0.4.0
// Date:    2026-10-28
import { BudgetExhausted, Net } from "./http";
import * as M from "./match";
import * as S from "./sources";
import { jobPostings, readHtml } from "./extract";
import DEFAULTS from "./shared/search_defaults.json";
import VOCAB from "./shared/skill_vocabulary.json";

export interface Env {
  DB: D1Database;
  APP_PASSWORD?: string; SYNC_TOKEN?: string;
  JSEARCH_API_KEY?: string; ADZUNA_APP_ID?: string; ADZUNA_APP_KEY?: string;
  RUN_HOUR_UTC?: string;
}

export const today = () => new Date().toISOString().slice(0, 10);
const now = () => new Date().toISOString().slice(0, 19) + "Z";

// ----------------------------------------------------------------- config
export async function getConfig<T = any>(db: D1Database, k: string, fallback: T): Promise<T> {
  const row = await db.prepare("SELECT v FROM config WHERE k = ?").bind(k).first<{ v: string }>();
  if (!row) return fallback;
  try { return JSON.parse(row.v) as T; } catch { return fallback; }
}
export async function setConfig(db: D1Database, k: string, v: unknown) {
  await db.prepare("INSERT OR REPLACE INTO config (k, v) VALUES (?, ?)").bind(k, JSON.stringify(v)).run();
}

const blank = (v: unknown) => v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0) ||
  (typeof v === "object" && !Array.isArray(v) && Object.keys(v as object).length === 0);

/** The user's search config over the engine defaults (a blank value keeps the default). */
export async function searchConfig(db: D1Database): Promise<any> {
  const user = await getConfig<any>(db, "search_config", {});
  const out: any = { ...DEFAULTS };
  for (const [k, v] of Object.entries(user)) if (!k.startsWith("_") && !blank(v)) out[k] = v;
  out.sources = { ...(DEFAULTS as any).sources, ...(user.sources ?? {}) };
  return out;
}

export async function employers(db: D1Database): Promise<{ name: string; urls: string[]; ats?: any }[]> {
  const e = await getConfig<any>(db, "employers", { employers: [] });
  const ex = new Set((e.exclude ?? []).map((x: string) => x.toLowerCase()));
  return (e.employers ?? []).filter((x: any) => x?.name && !ex.has(String(x.name).toLowerCase()));
}

export async function keys(env: Env) {
  const k = await getConfig<any>(env.DB, "keys", {});
  return { jsearch: env.JSEARCH_API_KEY || k.jsearch_api_key || "", jsearch_host: k.jsearch_host || "openwebninja",
           adzuna_id: env.ADZUNA_APP_ID || k.adzuna_app_id || "", adzuna_key: env.ADZUNA_APP_KEY || k.adzuna_app_key || "" };
}

// -------------------------------------------------------------------- log
export async function log(db: D1Database, line: string) {
  await db.prepare("INSERT INTO log (ts, line) VALUES (?, ?)").bind(now(), line.slice(0, 600)).run();
}

async function bump(db: D1Database, runId: number, field: string, by = 1) {
  await db.prepare(`UPDATE runs SET summary = json_set(summary, '$.${field}', coalesce(json_extract(summary, '$.${field}'), 0) + ?) WHERE id = ?`)
    .bind(by, runId).run();
}

// ---------------------------------------------------------------- planning
const locName = (l: M.Location) => (typeof l === "string" ? l : l.name);
const locCountry = (l: M.Location) => (typeof l === "string" ? "" : String(l.country ?? "").toLowerCase());

/** Queues one run. mode: 'weekly' (collect + verify) | 'daily' (collect) | 'verify' | 'fetch'. */
export async function planRun(env: Env, mode: string, extra: any = {}): Promise<number> {
  const db = env.DB, cfg = await searchConfig(db), src = cfg.sources ?? {};
  const kw: string[] = cfg.keywords ?? [], locs: M.Location[] = cfg.locations ?? [];
  const run = await db.prepare("INSERT INTO runs (day, mode, started, summary) VALUES (?, ?, ?, ?) RETURNING id")
    .bind(today(), mode, now(), JSON.stringify({ new: 0, candidates: 0, already: 0, errors: 0, expired: 0 })).first<{ id: number }>();
  const runId = run!.id;
  const tasks: [string, any][] = [];
  if (mode === "fetch") tasks.push(["fetch_url", extra]);
  if ((mode === "weekly" || mode === "daily") && kw.length && locs.length) {
    if (src.jobtech !== false) for (const k of kw) tasks.push(["jobtech", { kw: k }]);
    if (src.employer_sites !== false) {
      for (const e of await employers(db)) {
        for (const url of e.urls?.length ? e.urls : [""]) {
          const [kind, p] = S.detectAts(url, e.ats);
          if (kind === "agent_only") continue;
          if (kind === "workday") for (const k of kw) tasks.push(["workday", { ...p, employer: e.name, kw: k }]);
          else tasks.push([kind, { ...p, employer: e.name, url: p.url ?? url }]);
        }
      }
    }
    const k = await keys(env);
    if (src.jsearch && k.jsearch) {
      for (const l of locs) {
        if (!locCountry(l)) continue;
        for (const w of kw) tasks.push(["jsearch", { kw: w, place: locName(l), country: locCountry(l), key: "", host: k.jsearch_host, pages_left: Number(src.jsearch_pages ?? 1) }]);
      }
    }
    if (src.adzuna && k.adzuna_id && k.adzuna_key) {
      for (const l of locs) if (S.adzunaCovers(locCountry(l))) for (const w of kw) tasks.push(["adzuna", { kw: w, place: locName(l), country: locCountry(l) }]);
    }
    if (src.hn_who_is_hiring) tasks.push(["hn", {}]);
    if (src.yc_jobs) tasks.push(["yc", {}]);
  }
  if (mode === "weekly" || mode === "verify") {
    const rows = await db.prepare("SELECT key FROM postings WHERE status NOT LIKE 'Rejected%' AND status != 'Expired'").all<{ key: string }>();
    for (const r of rows.results ?? []) tasks.push(["verify", { key: r.key }]);
  }
  const stmt = db.prepare("INSERT INTO tasks (run_id, kind, payload, created_at) VALUES (?, ?, ?, ?)");
  for (let i = 0; i < tasks.length; i += 50) {
    await db.batch(tasks.slice(i, i + 50).map(([kind, p]) => stmt.bind(runId, kind, JSON.stringify(p), now())));
  }
  await log(db, `run ${mode} ${today()}: ${tasks.length} task(s) queued`);
  if (!tasks.length) await finishRun(db, runId);
  return runId;
}

/** Starts the day's run once, after RUN_HOUR_UTC. Search day: collect + verify; other days: collect. */
export async function maybeStartDaily(env: Env) {
  const hour = Number(env.RUN_HOUR_UTC ?? "6");
  if (new Date().getUTCHours() < hour) return;
  const done = await env.DB.prepare("SELECT id FROM runs WHERE day = ? AND mode IN ('weekly', 'daily') LIMIT 1").bind(today()).first();
  if (done) return;
  const cfg = await searchConfig(env.DB);
  if (blank(cfg.keywords) || blank(cfg.locations)) return;
  const day = String(cfg.weekly_list?.full_search_day ?? "Monday").toLowerCase();
  const isDay = new Date().toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" }).toLowerCase() === day;
  if (!isDay && cfg.cloud?.daily_search === false) return;
  await planRun(env, isDay ? "weekly" : "daily");
}

// ------------------------------------------------------------ task queue
interface Task { id: number; run_id: number; kind: string; payload: string; attempts: number }

async function claim(db: D1Database): Promise<Task | null> {
  // a task whose run was cut off (time or CPU limit) is retried after 10 minutes, at most 3 times
  await db.prepare("UPDATE tasks SET state = CASE WHEN attempts >= 3 THEN 'failed' ELSE 'pending' END WHERE state = 'running' AND claimed_at < ?")
    .bind(Date.now() - 10 * 60_000).run();
  return db.prepare(`UPDATE tasks SET state = 'running', attempts = attempts + 1, claimed_at = ?
                     WHERE id = (SELECT id FROM tasks WHERE state = 'pending' ORDER BY id LIMIT 1) AND state = 'pending'
                     RETURNING id, run_id, kind, payload, attempts`).bind(Date.now()).first<Task>();
}

/** Works through queued tasks within one invocation's budget. Returns how many were done. */
export async function drain(env: Env, maxTasks = 3, fetcher?: typeof fetch): Promise<number> {
  const net = new Net(env.DB, 44, fetcher);
  let n = 0;
  while (n < maxTasks && net.left >= 18) {
    const t = await claim(env.DB);
    if (!t) break;
    try {
      await runTask(env, net, t);
      await env.DB.prepare("UPDATE tasks SET state = 'done', result = 'ok' WHERE id = ?").bind(t.id).run();
    } catch (e) {
      if (e instanceof BudgetExhausted) {
        await env.DB.prepare("UPDATE tasks SET state = 'pending', attempts = attempts - 1 WHERE id = ?").bind(t.id).run();
        break;
      }
      const failed = t.attempts >= 3;
      await env.DB.prepare("UPDATE tasks SET state = ?, result = ? WHERE id = ?").bind(failed ? "failed" : "pending", String(e).slice(0, 300), t.id).run();
      if (failed) await log(env.DB, `task ${t.kind} failed: ${String(e).slice(0, 200)}`);
    }
    n++;
    const left = await env.DB.prepare("SELECT count(*) AS c FROM tasks WHERE run_id = ? AND state IN ('pending', 'running')").bind(t.run_id).first<{ c: number }>();
    if (!left?.c) await finishRun(env.DB, t.run_id);
  }
  return n;
}

async function finishRun(db: D1Database, runId: number) {
  const r = await db.prepare("UPDATE runs SET finished = ? WHERE id = ? AND finished IS NULL RETURNING mode, summary").bind(now(), runId).first<{ mode: string; summary: string }>();
  if (!r) return;
  const s = JSON.parse(r.summary || "{}");
  await log(db, `run ${r.mode} finished: ${s.candidates ?? 0} listing(s), ${s.new ?? 0} new, ${s.already ?? 0} already tracked`
    + (s.expired ? `, ${s.expired} expired` : "") + (s.errors ? `, ${s.errors} source error(s)` : ""));
}

async function queue(db: D1Database, runId: number, kind: string, payload: any) {
  await db.prepare("INSERT INTO tasks (run_id, kind, payload, created_at) VALUES (?, ?, ?, ?)").bind(runId, kind, JSON.stringify(payload), now()).run();
}

async function runTask(env: Env, net: Net, t: Task) {
  const db = env.DB, p = JSON.parse(t.payload || "{}");
  const cfg = await searchConfig(db);
  const kw: string[] = cfg.keywords ?? [];
  let page: S.Page | null = null;
  switch (t.kind) {
    case "jobtech": page = await S.jobtech(net, p); break;
    case "greenhouse": page = await S.greenhouse(net, p); break;
    case "lever": page = await S.lever(net, p); break;
    case "ashby": page = await S.ashby(net, p); break;
    case "workday": page = await S.workday(net, p); break;
    case "smartrecruiters": page = await S.smartrecruiters(net, p); break;
    case "html": page = await S.htmlPage(net, { url: p.url, employer: p.employer, keywords: kw }); break;
    case "jsearch": { const k = await keys(env); page = await S.jsearch(net, { ...p, key: k.jsearch }); break; }
    case "adzuna": { const k = await keys(env); page = await S.adzuna(net, { ...p, id: k.adzuna_id, key: k.adzuna_key }); break; }
    case "hn": page = await S.hnThread(net, p); break;
    case "yc": page = await S.ycList(net); break;
    case "yc_item": page = await S.ycItem(net, p); break;
    case "detail": return detailTask(env, net, t.run_id, p);
    case "verify": return verifyTask(env, net, t.run_id, p.key);
    case "fetch_url": return fetchTask(env, net, t.run_id, p);
    default: return;
  }
  if (page.error) { await bump(db, t.run_id, "errors"); await log(db, `[source error] ${page.error}`); }
  if (page.next) await queue(db, t.run_id, t.kind, page.next);
  for (const x of page.tasks ?? []) await queue(db, t.run_id, x.kind, x.payload);
  await bump(db, t.run_id, "candidates", page.candidates.length);
  for (const c of page.candidates) await consider(env, t.run_id, c, cfg, false);
}

// ------------------------------------------------------------- filtering
/** Port of _filter_and_build for one candidate: drop, queue a detail fetch, or store. */
async function consider(env: Env, runId: number, c: S.Candidate, cfg: any, explicit: boolean, detailDone = false) {
  const db = env.DB;
  const kw: string[] = cfg.keywords ?? [], locs: M.Location[] = cfg.locations ?? [];
  const scope = cfg.match_scope ?? "title", exclude = cfg.exclude_terms ?? [];
  let [hit, where] = M.matchKeywords(c.title, (c.description || "") + " " + (c.skills || []).join(" "), kw, scope, exclude);
  if (explicit && !hit.length) [hit, where] = [["(none)"], "description"];
  if (!hit.length) return;
  if (c.detail && !c.description && !detailDone) {
    if (await isTracked(db, c)) { await bump(db, runId, "already"); return; }
    if (cfg.sources?.confirm_leads === false && c.lead) { /* keep as unconfirmed lead */ }
    else { await queue(db, runId, "detail", { c, explicit }); return; }
  }
  const remoteOk = cfg.work_arrangement?.remote_ok ?? true;
  let loc = M.matchLocation(c.location_text, locs, remoteOk, c.is_remote);
  if (loc === null && explicit) loc = "given";
  if (loc === null) {
    const vague = /^\s*\d+\s+locations?\s*$/i.test(c.location_text || "");
    if (c.lead || !c.location_text || vague) loc = "unknown";
    else return;
  }
  const runDate = today();
  const stated = M.statedDeadline(c.description), boardDeadline = c.deadline || "";
  if (stated) c.deadline = stated;
  const sen = M.seniority(c.title);
  const vocab = [...(cfg.skill_terms ?? []), ...kw, ...((VOCAB as any).terms ?? [])];
  const skills = (c.skills || []).join(", ") || M.skillsSummary(c.description, vocab);
  const notes = [`Source: ${c.source}`, `auto-collected ${runDate} (online)`, explicit ? "added from a link" : `matched ${hit.join(", ")} in ${where}`];
  if (loc === "unknown") notes.push("location not stated in listing, check");
  if (c.lead) notes.push("link from careers page, open to confirm it is a live posting");
  if (c.posted_text && !c.published) notes.push(`posted: ${c.posted_text}`);
  if (stated && boardDeadline && stated !== boardDeadline) notes.push(`deadline ${stated} as stated in the posting (job board says ${boardDeadline})`);
  if (M.seniorityBucket(sen, cfg.seniority) === "senior" && M.welcomesJunior(c.description)) notes.push(`seniority flag (${sen}) may not apply: the posting says junior applicants are welcome`);
  if (c.apply_url && c.apply_url !== c.url) notes.push(`apply: ${c.apply_url}`);
  if (await isTracked(db, c)) { await bump(db, runId, "already"); return; }
  const key = `${c.url}||${c.title.trim()}`;
  const res = await db.prepare(`INSERT OR IGNORE INTO postings (key, url, title, employer, location, category, seniority, announced, deadline,
      arrangement, skills, status, notes, description, source, found, norm, lead, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).bind(
    key, c.url, c.title.trim(), c.employer, c.location_text, M.category(c.title, c.description, cfg.categories ?? [], cfg.category_rules ?? {}),
    sen, c.published, c.deadline || "rolling", M.arrangement(c.workplace, c.location_text, (c.description || "").slice(0, 1500)),
    skills || "not extracted, see posting", c.lead ? "Unverified" : "New", notes.join("; "), (c.description || "").slice(0, 20000),
    c.source, runDate, M.normKey(c.employer, c.title), c.lead ? 1 : 0, now()).run();
  if (res.meta.changes) { await bump(db, runId, "new"); if (explicit) await log(db, `added: ${c.employer}: ${c.title}`); }
  else await bump(db, runId, "already");
}

async function isTracked(db: D1Database, c: S.Candidate): Promise<boolean> {
  const r = await db.prepare("SELECT 1 FROM postings WHERE key = ? OR url = ? OR (? != '' AND url = ?) OR norm = ? LIMIT 1")
    .bind(`${c.url}||${c.title.trim()}`, c.url, c.apply_url || "", c.apply_url || "", M.normKey(c.employer, c.title)).first();
  return !!r;
}

async function detailTask(env: Env, net: Net, runId: number, p: { c: S.Candidate; explicit?: boolean }) {
  const c = p.c;
  const e = await S.fillDetail(net, c);
  if (e) await log(env.DB, e);
  await consider(env, runId, c, await searchConfig(env.DB), !!p.explicit, true);
}

async function fetchTask(env: Env, net: Net, runId: number, p: { url: string; employer?: string; title?: string }) {
  const r = await net.getPage(p.url);
  if (!r.ok) { await log(env.DB, `could not read ${p.url}: ${r.error || "HTTP " + r.status}`); return; }
  const d = readHtml(r.text, r.url || p.url);
  const c: S.Candidate = { title: p.title || d.title, employer: p.employer || d.employer, location_text: d.location_text, url: p.url,
    apply_url: "", published: d.published, deadline: d.deadline, description: d.description, is_remote: d.is_remote, workplace: "",
    employment_type: d.employment_type, skills: [], source: `Fetched page (${d.how})` };
  await log(env.DB, `read ${p.url} (${d.how}${d.complete ? "" : ", INCOMPLETE"}): ${d.description.length} characters`);
  if (!d.complete) await log(env.DB, "this page is probably built in the browser; add it in the Job Agent app on your computer, which can render it");
  if (!c.title || !c.employer) { await log(env.DB, "not added: title or employer unknown; give them in the form"); return; }
  await consider(env, runId, c, await searchConfig(env.DB), true, true);
}

// -------------------------------------------------------------- verifying
const CLOSED_TEXT = /(no longer (available|accepting)|position (has been )?(filled|closed)|annonsen (är|har) (inte längre|tagits bort)|job not found)/i;

async function verifyTask(env: Env, net: Net, runId: number, key: string) {
  const db = env.DB;
  const row = await db.prepare("SELECT key, url, status, notes, deadline FROM postings WHERE key = ?").bind(key).first<any>();
  if (!row) return;
  const url: string = row.url || "";
  let res = "live";
  if (/^\d{4}-\d{2}-\d{2}$/.test(row.deadline || "") && row.deadline < today()) res = `closed:deadline ${row.deadline} passed`;
  else if (!/^https?:/.test(url) || url.includes("linkedin.com") || url.includes("indeed.")) return;
  else {
    const ad = /arbetsformedlingen\.se\/platsbanken\/annonser\/(\d+)/.exec(url)?.[1];
    if (ad) {
      const st = await S.jobtechAdStatus(net, ad);
      res = st === "removed" ? "closed:removed from Platsbanken" : st === "live" ? "live" : "unknown:Platsbanken API not reachable";
    } else {
      const r = await net.getPage(url);
      if (r.status === 404 || r.status === 410) res = `closed:HTTP ${r.status}`;
      else if (!r.ok) res = `unknown:${r.error || "HTTP " + r.status}`;
      else {
        for (const jp of jobPostings(r.text)) {
          const vt = M.isoDay(jp.validThrough);
          if (vt && vt < today()) res = `closed:validThrough ${vt}`;
        }
        if (res === "live" && CLOSED_TEXT.test(r.text)) res = "closed:page says the posting is closed";
      }
    }
  }
  const [kind, ...rest] = res.split(":");
  const why = rest.join(":");
  if (kind === "live") return;
  if (kind === "closed") {
    if (String(row.status).startsWith("Approved")) {
      await db.prepare("UPDATE postings SET notes = notes || ?, updated_at = ? WHERE key = ?").bind(` | ${today()}: looks closed (${why}), kept because accepted`, now(), key).run();
    } else {
      await db.prepare("UPDATE postings SET status = 'Expired', notes = notes || ?, updated_at = ? WHERE key = ?").bind(` | ${today()}: expired (${why})`, now(), key).run();
      await bump(db, runId, "expired");
    }
  } else if (!String(row.notes || "").includes(`could not verify (${why})`)) {
    await db.prepare("UPDATE postings SET notes = notes || ?, updated_at = ? WHERE key = ?").bind(` | ${today()}: could not verify (${why})`, now(), key).run();
  }
}
