// Job-search agent engine, online search
// File:    cloud/src/index.ts
// Purpose: The Worker: login, the app's API (same as the local app, search-only), the sync API for your computer, and the cron that runs searches.
// Author:  manpmanp <manp.node@gmail.com>
// Generated with Claude (Anthropic), under the author's direction and review.
// License: MIT (see LICENSE)
// Version: 0.4.0
// Date:    2026-10-28
//
// Your postings, decisions and search settings live in this Worker's D1
// database on your own Cloudflare account. CVs, cover letters and generated
// documents never come here: the Job Agent app on your computer pulls the
// accepted postings and makes the documents locally.
import APP_HTML from "./shared/index.html";
import FORM_HTML from "./shared/candidate_form.html";
import JOB_SITES from "./shared/job_sites.json";
import * as P from "./pipeline";
import { seniorityBucket } from "./match";

type Env = P.Env;
const VERSION = "0.4.0";
const SESSION_DAYS = 14;
const enc = new TextEncoder();

// ---------------------------------------------------------------- crypto
async function hmac(keyText: string, msg: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", enc.encode(keyText), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(msg)));
  return btoa(String.fromCharCode(...sig)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function same(a: string, b: string): boolean {
  const x = enc.encode(a), y = enc.encode(b);
  if (x.length !== y.length) return false;
  return (crypto.subtle as any).timingSafeEqual ? (crypto.subtle as any).timingSafeEqual(x, y) : x.every((v, i) => v === y[i]);
}
const sessionKey = (env: Env) => "job-agent-session:" + (env.APP_PASSWORD ?? "");

async function session(req: Request, env: Env): Promise<string | null> {
  const c = /(?:^|;\s*)ja=([^;]+)/.exec(req.headers.get("Cookie") || "")?.[1];
  if (!c) return null;
  const [exp, sig] = c.split(".");
  if (!exp || !sig || Number(exp) < Date.now()) return null;
  return same(sig, await hmac(sessionKey(env), "s:" + exp)) ? exp : null;
}
const csrf = (env: Env, exp: string) => hmac(sessionKey(env), "csrf:" + exp);

// --------------------------------------------------------------- helpers
const json = (data: unknown, status = 200, extra: HeadersInit = {}) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extra } });
const SEC_HEADERS = {
  "Content-Security-Policy": "default-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'self'",
  "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
};
const html = (body: string, status = 200, extra: HeadersInit = {}) =>
  new Response(body, { status, headers: { "Content-Type": "text/html; charset=utf-8", ...SEC_HEADERS, ...extra } });

function loginPage(msg = "") {
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Agent</title><style>
:root{--bg:#f4f6f8;--panel:#fff;--b:#d9dee5;--t:#1c232b;--m:#5f6b78;--a:#1B3A5C}
@media (prefers-color-scheme: dark){:root{--bg:#101419;--panel:#181e25;--b:#2b333d;--t:#e4e8ee;--m:#98a3b1;--a:#9dbde3}}
body{margin:0;background:var(--bg);color:var(--t);font:15px/1.45 Arial,sans-serif;display:grid;place-items:center;min-height:100vh;padding:16px;box-sizing:border-box}
form{background:var(--panel);border:1px solid var(--b);border-radius:12px;padding:24px;width:min(360px,100%)}
h1{font-size:19px;color:var(--a);margin:0 0 6px}p{color:var(--m);margin:0 0 14px;font-size:13px}
input{width:100%;box-sizing:border-box;font:inherit;padding:10px;border:1px solid var(--b);border-radius:8px;background:var(--bg);color:var(--t)}
button{margin-top:12px;width:100%;font:inherit;font-weight:bold;padding:10px;border:0;border-radius:8px;background:var(--a);color:var(--panel);cursor:pointer}
.e{color:#b03a3a;font-size:13px;margin-top:10px}</style></head><body>
<form method="post" action="/login"><h1>Job Agent</h1><p>Your online job search. Enter the password you chose when you deployed it.</p>
<input type="password" name="password" autocomplete="current-password" autofocus required aria-label="Password">
<button type="submit">Open</button>${msg ? `<div class="e">${msg}</div>` : ""}</form></body></html>`;
}

async function inject(page: string, env: Env, exp: string, extra = "") {
  const token = await csrf(env, exp);
  return page.replace("</head>", `<script>window.JOB_AGENT_API = ${JSON.stringify({ token })}; window.JOB_AGENT_CLOUD = true;${extra}</script>\n</head>`);
}

const decisionOf = (status: string) => (status.startsWith("Approved") ? "accepted" : status.startsWith("Rejected") ? "rejected" : "");
const APPROVED = "Approved - ready for tailored documents";

async function applyDecision(env: Env, key: string, d: { decision: string; reasons?: string[]; note?: string; ts?: string }) {
  const ts = d.ts || new Date().toISOString().slice(0, 19);
  const row = await env.DB.prepare("SELECT status, notes FROM postings WHERE key = ?").bind(key).first<{ status: string; notes: string }>();
  if (!row) return false;
  if (d.decision === "undo") {
    await env.DB.batch([
      env.DB.prepare("DELETE FROM decisions WHERE key = ?").bind(key),
      env.DB.prepare("UPDATE postings SET status = 'New', notes = notes || ?, updated_at = ? WHERE key = ?").bind(` | Decision undone (${ts})`, ts, key),
    ]);
    return true;
  }
  const reasons = d.decision === "rejected" ? (d.reasons?.length ? d.reasons : ["Not specified"]).map(String) : [];
  const status = d.decision === "accepted" ? APPROVED : `Rejected: ${reasons.join("; ")}`;
  const note = d.decision === "accepted" ? ` | Accepted online (${ts})` : ` | Rejected online (${ts}): ${reasons.join("; ")}${d.note ? " - " + d.note : ""}`;
  await env.DB.batch([
    env.DB.prepare("INSERT OR REPLACE INTO decisions (key, decision, reasons, note, ts) VALUES (?, ?, ?, ?, ?)")
      .bind(key, d.decision, JSON.stringify(reasons), String(d.note ?? "").slice(0, 500), ts),
    env.DB.prepare("UPDATE postings SET status = ?, notes = notes || ?, updated_at = ? WHERE key = ?").bind(status, note, ts, key),
  ]);
  return true;
}

function actionFor(deadline: string, announced: string, actAsap: number) {
  const t = new Date(P.today() + "T00:00:00Z").getTime();
  if (/^\d{4}-\d{2}-\d{2}$/.test(deadline)) {
    const days = (new Date(deadline + "T00:00:00Z").getTime() - t) / 86400000;
    return days >= 0 && days <= 1 ? "⚠ ACT IMMEDIATELY" : "";
  }
  if (/rolling/i.test(deadline) && /^\d{4}-\d{2}-\d{2}$/.test(announced)) {
    const days = Math.round((t - new Date(announced + "T00:00:00Z").getTime()) / 86400000);
    if (days > actAsap) return `⚠ ACT ASAP (${days}d since posting)`;
  }
  return "";
}

// ------------------------------------------------------------------ API
async function status(env: Env, url: URL) {
  const cfg = await P.searchConfig(env.DB);
  const kw = cfg.keywords ?? [], locs = cfg.locations ?? [];
  const c = await env.DB.prepare(`SELECT
      sum(CASE WHEN status NOT LIKE 'Rejected%' AND status != 'Expired' THEN 1 ELSE 0 END) AS active,
      sum(CASE WHEN status NOT LIKE 'Rejected%' AND status != 'Expired' AND status NOT LIKE 'Approved%' THEN 1 ELSE 0 END) AS undecided,
      sum(CASE WHEN status LIKE 'Approved%' THEN 1 ELSE 0 END) AS accepted,
      sum(CASE WHEN status LIKE 'Rejected%' THEN 1 ELSE 0 END) AS rejected,
      sum(CASE WHEN status = 'Expired' THEN 1 ELSE 0 END) AS expired FROM postings`).first<any>();
  const recent = await env.DB.prepare("SELECT ts, line FROM log ORDER BY id DESC LIMIT 14").all<{ ts: string; line: string }>();
  const searchOn = kw.length > 0 && locs.length > 0;
  const hour = Number(env.RUN_HOUR_UTC ?? "6");
  return {
    mode: "cloud", version: VERSION, home: url.origin, today: P.today(),
    capabilities: {
      search: { on: searchOn, why: searchOn ? `${kw.length} keyword(s) x ${locs.length} location(s)` : "add keywords and locations in Setup" },
      tailoring_full: { on: false, why: "documents are made on your computer" },
    },
    counts: { active: c?.active ?? 0, undecided: c?.undecided ?? 0, accepted_waiting: c?.accepted ?? 0, rejected: c?.rejected ?? 0, expired: c?.expired ?? 0 },
    schedule: { on: true, text: `searches every day after ${String(hour).padStart(2, "0")}:00 UTC` },
    api_key: false, awaiting_extraction: [], open_conflicts: [],
    recent: (recent.results ?? []).map((r) => `${r.ts.slice(0, 16).replace("T", " ")}  ${r.line}`),
    job: await currentJob(env),
    search_day: cfg.weekly_list?.full_search_day ?? "Monday",
    sync_ready: !!env.SYNC_TOKEN,
  };
}

async function currentJob(env: Env) {
  const run = await env.DB.prepare("SELECT id, mode, started, finished, summary FROM runs ORDER BY id DESC LIMIT 1").first<any>();
  if (!run) return null;
  const left = await env.DB.prepare("SELECT count(*) AS c FROM tasks WHERE run_id = ? AND state IN ('pending', 'running')").bind(run.id).first<{ c: number }>();
  const total = await env.DB.prepare("SELECT count(*) AS c FROM tasks WHERE run_id = ?").bind(run.id).first<{ c: number }>();
  const lines = await env.DB.prepare("SELECT line FROM log WHERE ts >= ? ORDER BY id LIMIT 60").bind(run.started).all<{ line: string }>();
  const s = JSON.parse(run.summary || "{}");
  const label = { weekly: "Search now", daily: "Daily search", verify: "Check postings", fetch: "Add a posting" }[run.mode as string] ?? run.mode;
  const done = !!run.finished;
  return { id: run.id, label, done, ok: done ? true : null, started: run.started,
           lines: [...(lines.results ?? []).map((l) => l.line),
                   ...(done ? [] : [`working: ${(total?.c ?? 0) - (left?.c ?? 0)} of ${total?.c ?? 0} step(s) done, ${s.new ?? 0} new so far`])] };
}

async function postings(env: Env) {
  const cfg = await P.searchConfig(env.DB);
  const rows = await env.DB.prepare("SELECT key, url, title, employer, location, category, seniority, announced, deadline, arrangement, skills, status, notes, found FROM postings ORDER BY found DESC, rowid DESC LIMIT 2000").all<any>();
  const act = Number(cfg.act_asap_after_days ?? 7);
  return {
    rejection_reasons: cfg.rejection_reasons ?? [],
    postings: (rows.results ?? []).map((r) => ({
      key: r.key, title: r.title, employer: r.employer, location: r.location, category: r.category, seniority: r.seniority,
      senior_bucket: seniorityBucket(r.seniority, cfg.seniority), announced: r.announced, deadline: r.deadline, found: r.found,
      arrangement: r.arrangement, skills: r.skills, url: r.url, status: r.status,
      bucket: r.status === "Expired" ? "expired" : String(r.status).startsWith("Rejected") ? "rejected" : "active",
      notes: r.notes, drafted: String(r.notes || "").includes("Documents made on your computer"),
      urgent: actionFor(r.deadline || "", r.announced || "", act), docs: [],
    })),
  };
}

async function api(req: Request, env: Env, ctx: ExecutionContext, url: URL): Promise<Response> {
  const p = url.pathname, db = env.DB;
  const body = req.method === "POST" ? await req.json<any>().catch(() => ({})) : {};
  if (p === "/api/status") return json(await status(env, url));
  if (p === "/api/postings") return json(await postings(env));
  if (p === "/api/job") {
    // while someone watches, each poll also does a little of the queued work
    try { await P.drain(env, 2); } catch (e) { await P.log(db, `work step failed: ${String(e).slice(0, 200)}`); }
    return json({ job: await currentJob(env) });
  }
  if (p === "/api/decision" && req.method === "POST") {
    if (!["accepted", "rejected", "undo"].includes(body.decision)) return json({ error: "decision must be accepted, rejected or undo" }, 400);
    return (await applyDecision(env, String(body.key ?? ""), body)) ? json({ ok: true }) : json({ error: "posting not found" }, 404);
  }
  if ((p === "/api/run" || p === "/api/verify") && req.method === "POST") {
    const running = await db.prepare("SELECT id FROM runs WHERE finished IS NULL LIMIT 1").first();
    if (running) return json({ error: "a search is already running" }, 409);
    await P.planRun(env, p === "/api/verify" ? "verify" : "weekly");
    ctx.waitUntil(P.drain(env, 2).catch(() => 0));
    return json({ job: await currentJob(env) });
  }
  if (p === "/api/fetch" && req.method === "POST") {
    const link = String(body.url ?? "").trim();
    if (!/^https?:\/\//.test(link)) return json({ error: "give a web address starting with http:// or https://" }, 400);
    await P.planRun(env, "fetch", { url: link, employer: String(body.employer ?? "").trim(), title: String(body.title ?? "").trim() });
    return json({ job: await currentJob(env) });
  }
  if (p === "/api/search_config") {
    if (req.method === "POST") {
      const cur = await P.getConfig<any>(db, "search_config", {});
      for (const [k, v] of Object.entries(body)) if (!k.startsWith("_")) cur[k] = v;
      await P.setConfig(db, "search_config", cur);
      const cfg = await P.searchConfig(db);
      return json({ saved: "online", search_ready: !!(cfg.keywords?.length && cfg.locations?.length) });
    }
    return json(await P.getConfig(db, "search_config", {}));
  }
  if (p === "/api/employers") {
    if (req.method === "POST") {
      const list = (Array.isArray(body.employers) ? body.employers : []).filter((e: any) => e?.name).map((e: any) => ({
        name: String(e.name).slice(0, 120), urls: (e.urls ?? []).map(String).filter((u: string) => /^https?:\/\/|^(indeed|linkedin):/.test(u)).slice(0, 5) }));
      await P.setConfig(db, "employers", { mode: "override", employers: list.slice(0, 200) });
    }
    return json(await P.getConfig(db, "employers", { employers: [] }));
  }
  if (p === "/api/settings") {
    if (req.method === "POST") {
      const cfg = await P.getConfig<any>(db, "search_config", {});
      if (body.sources && typeof body.sources === "object") cfg.sources = { ...(cfg.sources ?? {}), ...body.sources };
      await P.setConfig(db, "search_config", cfg);
      const k = await P.getConfig<any>(db, "keys", {});
      for (const [n, v] of Object.entries(body.secrets ?? {})) {
        if (!["jsearch_api_key", "jsearch_host", "adzuna_app_id", "adzuna_app_key"].includes(n) || v === "" || v === null) continue;
        if (v === "__clear__") delete k[n]; else k[n] = String(v).trim();
      }
      await P.setConfig(db, "keys", k);
    }
    const cfg = await P.searchConfig(db), k = await P.keys(env);
    return json({ secrets: { jsearch_api_key: !!k.jsearch, adzuna_app_id: !!k.adzuna_id, adzuna_app_key: !!k.adzuna_key, anthropic_api_key: false },
                  jsearch_host: k.jsearch_host, sources: cfg.sources ?? {}, enrichment: {}, documents: {} });
  }
  if (p === "/api/job_sites") return json(JOB_SITES);
  if (p === "/api/info") {
    const cfg = await P.searchConfig(db);
    return json({ home: url.origin, intake: {}, sources: [], search_ready: !!(cfg.keywords?.length && cfg.locations?.length), tailoring: "template" });
  }
  if (p === "/api/profile") return json({});
  return json({ error: "not available online: documents and your CV are handled by the app on your computer" }, 404);
}

// -------------------------------------------------- sync API (your computer)
async function syncApi(req: Request, env: Env, url: URL): Promise<Response> {
  const auth = req.headers.get("Authorization") || "";
  if (!env.SYNC_TOKEN || !same(auth, `Bearer ${env.SYNC_TOKEN}`)) return json({ error: "wrong or missing sync token" }, 401);
  const db = env.DB;
  if (url.pathname === "/api/sync/export") {
    const since = url.searchParams.get("since") || "";
    const rows = await db.prepare("SELECT * FROM postings WHERE coalesce(updated_at, '') >= ? ORDER BY found").bind(since).all<any>();
    const dec = await db.prepare("SELECT * FROM decisions").all<any>();
    return json({
      version: VERSION, now: new Date().toISOString().slice(0, 19) + "Z",
      config: { search_config: await P.getConfig(db, "search_config", {}), employers: await P.getConfig(db, "employers", { employers: [] }) },
      postings: rows.results ?? [],
      decisions: Object.fromEntries((dec.results ?? []).map((d) => [d.key, { decision: d.decision, reasons: JSON.parse(d.reasons || "[]"), note: d.note, ts: d.ts }])),
    });
  }
  if (url.pathname === "/api/sync/decisions" && req.method === "POST") {
    const body = await req.json<any>().catch(() => ({}));
    let applied = 0;
    for (const [key, d] of Object.entries<any>(body.decisions ?? {})) {
      const cur = await db.prepare("SELECT ts FROM decisions WHERE key = ?").bind(key).first<{ ts: string }>();
      if (cur && String(cur.ts) >= String(d.ts ?? "")) continue;   // the newer decision wins
      if (["accepted", "rejected"].includes(d.decision) && (await applyDecision(env, key, d))) applied++;
    }
    return json({ applied });
  }
  if (url.pathname === "/api/sync/drafted" && req.method === "POST") {
    const body = await req.json<any>().catch(() => ({}));
    for (const key of (body.keys ?? []).slice(0, 500)) {
      await db.prepare("UPDATE postings SET notes = notes || ?, updated_at = ? WHERE key = ? AND notes NOT LIKE '%Documents made on your computer%'")
        .bind(` | Documents made on your computer (${P.today()})`, new Date().toISOString().slice(0, 19), key).run();
    }
    return json({ ok: true });
  }
  if (url.pathname === "/api/sync/run" && req.method === "POST") {
    const running = await db.prepare("SELECT id FROM runs WHERE finished IS NULL LIMIT 1").first();
    if (running) return json({ ok: true, message: "a search is already running online" });
    await P.planRun(env, "weekly");
    return json({ ok: true, message: "search started online; it runs in the background (fetch again in a while)" });
  }
  if (url.pathname === "/api/sync/config" && req.method === "POST") {
    const body = await req.json<any>().catch(() => ({}));
    if (body.search_config && typeof body.search_config === "object") await P.setConfig(db, "search_config", body.search_config);
    if (body.employers && typeof body.employers === "object") await P.setConfig(db, "employers", body.employers);
    return json({ ok: true });
  }
  return json({ error: "not found" }, 404);
}

// ---------------------------------------------------------------- login
async function login(req: Request, env: Env): Promise<Response> {
  const ip = req.headers.get("CF-Connecting-IP") || "unknown";
  const row = await env.DB.prepare("SELECT failures, first_at FROM logins WHERE ip = ?").bind(ip).first<{ failures: number; first_at: number }>();
  const hour = 3600_000;
  if (row && row.failures >= 8 && Date.now() - row.first_at < hour) return html(loginPage("Too many attempts. Try again in an hour."), 429);
  const form = await req.formData().catch(() => null);
  const pw = String(form?.get("password") ?? "");
  if (!env.APP_PASSWORD || !same(pw, env.APP_PASSWORD)) {
    const fresh = !row || Date.now() - row.first_at >= hour;
    await env.DB.prepare("INSERT OR REPLACE INTO logins (ip, failures, first_at) VALUES (?, ?, ?)")
      .bind(ip, fresh ? 1 : row!.failures + 1, fresh ? Date.now() : row!.first_at).run();
    return html(loginPage("Wrong password."), 401);
  }
  await env.DB.prepare("DELETE FROM logins WHERE ip = ?").bind(ip).run();
  const exp = String(Date.now() + SESSION_DAYS * 86400_000);
  const cookie = `ja=${exp}.${await hmac(sessionKey(env), "s:" + exp)}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${SESSION_DAYS * 86400}`;
  return new Response(null, { status: 303, headers: { Location: "/", "Set-Cookie": cookie } });
}

// ---------------------------------------------------------------- worker
export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);
    if (!env.APP_PASSWORD || env.APP_PASSWORD.length < 8) {
      return html(`<p style="font-family:Arial;padding:24px">Set the APP_PASSWORD secret (at least 8 characters) for this Worker in the Cloudflare dashboard, then reload.</p>`, 503);
    }
    if (url.pathname === "/api/ping") return json({ app: "job-agent-engine", mode: "cloud", version: VERSION });
    if (url.pathname.startsWith("/api/sync/")) return syncApi(req, env, url);
    if (url.pathname === "/login" && req.method === "POST") return login(req, env);
    if (url.pathname === "/logout") return new Response(null, { status: 303, headers: { Location: "/", "Set-Cookie": "ja=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict" } });
    const exp = await session(req, env);
    if (!exp) return url.pathname.startsWith("/api/") ? json({ error: "not logged in" }, 401) : html(loginPage());
    if (url.pathname === "/" || url.pathname === "/index.html") return html(await inject(APP_HTML, env, exp));
    if (url.pathname === "/form") return html(await inject(FORM_HTML, env, exp, " window.JOB_AGENT_EMBEDDED = true;"));
    if (url.pathname.startsWith("/api/")) {
      if (!same(req.headers.get("X-Agent-Token") || "", await csrf(env, exp))) return json({ error: "missing or wrong token" }, 403);
      return api(req, env, ctx, url);
    }
    return json({ error: "not found" }, 404);
  },

  async scheduled(_ev: ScheduledController, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil((async () => {
      await P.maybeStartDaily(env);
      await P.drain(env, 3);
    })());
  },
};
