// Job-search agent engine, online search
// File:    cloud/src/http.ts
// Purpose: Polite fetch for the Worker: identification, robots.txt (RFC 9309), request budget, timeouts, size cap. Never throws on network errors.
// Author:  manpmanp <manp.node@gmail.com>
// Generated with Claude (Anthropic), under the author's direction and review.
// License: MIT (see LICENSE)
// Version: 0.4.0
// Date:    2026-10-28

export const USER_AGENT = "job-agent-engine/0.4.0 (personal job-search tool; reads public job postings)";
export const ROBOTS_TOKEN = "job-agent-engine";
const TIMEOUT_MS = 20_000;
const MAX_BYTES = 4 * 1024 * 1024;
const ROBOTS_TTL_S = 24 * 3600;

export class BudgetExhausted extends Error {}

export interface Resp { ok: boolean; status: number; text: string; url: string; error: string | null; contentType: string }

/** One per invocation: the Free plan allows 50 outgoing requests per run, a few are kept in reserve. */
export class Net {
  left: number;
  private lastHost = new Map<string, number>();
  private robotsMem = new Map<string, Rules>();
  // fetch must be called unbound in Workers (a stored reference called as a method throws "Illegal invocation")
  constructor(public db: D1Database | null, budget = 44, public fetcher: typeof fetch = (i, init) => fetch(i, init)) { this.left = budget; }

  async request(method: string, url: string, headers: Record<string, string> = {}, body?: unknown, checkRobots = false): Promise<Resp> {
    if (checkRobots && !(await this.robotsAllowed(url))) return { ok: false, status: 0, text: "", url, error: "disallowed by robots.txt", contentType: "" };
    if (this.left <= 0) throw new BudgetExhausted("request budget of this run used up");
    this.left--;
    const host = safeHost(url);
    const last = this.lastHost.get(host);
    if (last !== undefined) {
      const wait = 600 - (Date.now() - last);
      if (wait > 0) await new Promise((r) => setTimeout(r, wait));
    }
    this.lastHost.set(host, Date.now());
    const h: Record<string, string> = { "User-Agent": USER_AGENT, Accept: "application/json, text/html;q=0.9, */*;q=0.5", ...headers };
    let data: string | undefined;
    if (body !== undefined) { data = typeof body === "string" ? body : JSON.stringify(body); h["Content-Type"] ??= "application/json"; }
    try {
      const r = await this.fetcher(url, { method, headers: h, body: data, redirect: "follow", signal: AbortSignal.timeout(TIMEOUT_MS) });
      const len = Number(r.headers.get("content-length") || 0);
      if (len > MAX_BYTES) return { ok: false, status: r.status, text: "", url: r.url || url, error: "response too large", contentType: "" };
      const text = await r.text();
      return { ok: r.ok, status: r.status, text: text.length > MAX_BYTES ? "" : text, url: r.url || url, error: null,
               contentType: r.headers.get("content-type") || "" };
    } catch (e) {
      return { ok: false, status: 0, text: "", url, error: `${(e as Error).name}: ${(e as Error).message}`, contentType: "" };
    }
  }

  async getJson<T = any>(url: string, headers: Record<string, string> = {}): Promise<[Resp, T | null]> {
    const r = await this.request("GET", url, headers);
    return [r, r.ok ? parseJson<T>(r.text) : null];
  }

  async postJson<T = any>(url: string, body: unknown, headers: Record<string, string> = {}): Promise<[Resp, T | null]> {
    const r = await this.request("POST", url, headers, body);
    return [r, r.ok ? parseJson<T>(r.text) : null];
  }

  /** An ordinary web page: robots.txt is respected. */
  getPage(url: string): Promise<Resp> {
    if (!/^https?:\/\//i.test(url)) return Promise.resolve({ ok: false, status: 0, text: "", url, error: "not a web address", contentType: "" });
    return this.request("GET", url, { Accept: "text/html,application/xhtml+xml" }, undefined, true);
  }

  async robotsAllowed(url: string): Promise<boolean> {
    let u: URL;
    try { u = new URL(url); } catch { return false; }
    const origin = u.origin;
    let rules = this.robotsMem.get(origin);
    if (!rules && this.db) {
      const row = await this.db.prepare("SELECT rules, fetched_at FROM robots WHERE origin = ?").bind(origin).first<{ rules: string; fetched_at: number }>();
      if (row && Date.now() / 1000 - row.fetched_at < ROBOTS_TTL_S) rules = JSON.parse(row.rules) as Rules;
    }
    if (!rules) {
      const r = await this.request("GET", origin + "/robots.txt", { Accept: "text/plain" });
      if (r.ok) rules = parseRobots(r.text);
      else if (r.status >= 400 && r.status < 500 && ![401, 403, 429].includes(r.status)) rules = "all";
      else rules = "none";
      await this.db?.prepare("INSERT OR REPLACE INTO robots (origin, rules, fetched_at) VALUES (?, ?, ?)")
        .bind(origin, JSON.stringify(rules), Math.floor(Date.now() / 1000)).run();
    }
    this.robotsMem.set(origin, rules);
    return robotsAllow(rules, u.pathname + u.search);
  }
}

export function parseJson<T>(text: string): T | null {
  try { return JSON.parse(text) as T; } catch { return null; }
}

function safeHost(url: string): string {
  try { return new URL(url).host; } catch { return ""; }
}

// ------------------------------------------------------------- robots.txt
export type Rules = [boolean, string][] | "all" | "none";

export function parseRobots(text: string, token = ROBOTS_TOKEN): Rules {
  const groups: { agents: string[]; rules: [boolean, string][] }[] = [];
  let cur: (typeof groups)[number] | null = null;
  let lastAgent = false;
  for (const raw of text.split(/\r\n|\r|\n/)) {
    const line = raw.replace(/#.*$/, "").trim();
    const m = /^([a-z-]+)\s*:\s*(.*)$/i.exec(line);
    if (!m) continue;
    const key = m[1].toLowerCase(), value = m[2].trim();
    if (key === "user-agent") {
      if (!cur || !lastAgent) { cur = { agents: [], rules: [] }; groups.push(cur); }
      cur.agents.push(value.toLowerCase());
      lastAgent = true;
      continue;
    }
    lastAgent = false;
    if (cur && (key === "allow" || key === "disallow") && value) cur.rules.push([key === "allow", value]);
  }
  const own = groups.filter((g) => g.agents.includes(token.toLowerCase()));
  const chosen = own.length ? own : groups.filter((g) => g.agents.includes("*"));
  return chosen.flatMap((g) => g.rules);
}

function patternRe(p: string): RegExp {
  const anchored = p.endsWith("$");
  const body = (anchored ? p.slice(0, -1) : p).split("*").map((x) => x.replace(/[.+?^${}()|[\]\\]/g, "\\$&")).join(".*");
  return new RegExp("^" + body + (anchored ? "$" : ""));
}

export function robotsAllow(rules: Rules, path: string): boolean {
  if (rules === "all" || path === "/robots.txt") return true;
  if (rules === "none") return false;
  let best: [boolean, string] | null = null;
  for (const r of rules) {
    if (!patternRe(r[1]).test(path)) continue;
    if (!best || r[1].length > best[1].length || (r[1].length === best[1].length && r[0])) best = r;
  }
  return best ? best[0] : true;
}
