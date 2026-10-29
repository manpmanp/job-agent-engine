// End-to-end: the bundled Worker in Miniflare with a local D1; every outgoing
// request is served from tests/fixtures (the same recordings the Python tests use).
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { execSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { Miniflare } from "miniflare";

const FX = new URL("../../tests/fixtures/", import.meta.url);
const fx = (n: string) => readFileSync(new URL(n, FX), "utf8");
const gh = JSON.parse(fx("greenhouse_board.json"));

function route(url: string): [number, string] {
  if (url.includes("jobsearch.api.jobtechdev.se/search") && url.includes("q=FPGA")) return [200, fx("jobtech_fpga.json")];
  if (url.includes("jobsearch.api.jobtechdev.se/search")) return [200, fx("jobtech_empty.json")];
  if (url.includes("jobsearch.api.jobtechdev.se/ad/")) return [200, '{"removed": false}'];
  if (url.includes("boards-api.greenhouse.io/v1/boards/examplegh/jobs/")) {
    const id = Number(url.split("/").pop());
    return [200, JSON.stringify(gh.jobs.find((j: any) => j.id === id))];
  }
  if (url.includes("boards-api.greenhouse.io/v1/boards/examplegh/jobs")) return [200, JSON.stringify({ jobs: gh.jobs.map(({ content, ...j }: any) => j) })];
  if (url.includes("api.lever.co/v0/postings/examplelever")) return [200, fx("lever_board.json")];
  if (url.includes("api.ashbyhq.com/posting-api/job-board/exampleai")) return [200, fx("ashby_board.json")];
  if (url.includes("/wday/cxs/examplewd/External/jobs")) return [200, fx("workday_jobs.json")];
  if (url.includes("/wday/cxs/examplewd/External/job/")) return [200, JSON.stringify({ jobPostingInfo: { jobDescription: "<p>RTL design in SystemVerilog, UVM testbenches.</p>", startDate: "2026-10-25", remoteType: "Hybrid" } })];
  if (url.endsWith("/robots.txt")) return [404, ""];
  if (url.includes("jsonld.example/careers")) return [200, fx("career_jsonld.html")];
  if (url.includes("links.example/careers/fpga-developer")) return [200, fx("posting_structured.html")];
  if (url.includes("links.example/careers")) return [200, fx("career_links.html")];
  if (url.includes("plain.example/jobs/1")) return [200, fx("posting_plain.html")];
  return [404, ""];
}

let mf: Miniflare;
const calls: string[] = [];
const base = "http://job-agent.test";
let cookie = "", token = "";

async function req(path: string, init: RequestInit & { json?: unknown } = {}) {
  const headers: Record<string, string> = { ...(init.headers as any) };
  if (cookie) headers.Cookie = cookie;
  if (token) headers["X-Agent-Token"] = token;
  if (init.json !== undefined) { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(init.json); init.method ??= "POST"; }
  return mf.dispatchFetch(base + path, { ...init, headers, redirect: "manual" } as any);
}

beforeAll(async () => {
  execSync("npx wrangler deploy --dry-run --outdir dist", { cwd: new URL("..", import.meta.url), stdio: "pipe" });
  mf = new Miniflare({
    modules: true, modulesRoot: new URL("../dist/", import.meta.url).pathname,
    modulesRules: [{ type: "Text", include: ["**/*.html"] }], scriptPath: new URL("../dist/index.js", import.meta.url).pathname, compatibilityDate: "2026-08-01",
    d1Databases: ["DB"], bindings: { APP_PASSWORD: "correct horse battery", SYNC_TOKEN: "sync-secret-123", RUN_HOUR_UTC: "0" },
    outboundService: (r: Request) => { calls.push(r.url); const [s, b] = route(r.url); return new Response(b, { status: s }); },
  } as any);
  const db = await mf.getD1Database("DB");
  for (const f of readdirSync(new URL("../migrations/", import.meta.url)).sort()) {
    const sql = readFileSync(new URL("../migrations/" + f, import.meta.url), "utf8").replace(/--.*$/gm, "");
    for (const stmt of sql.split(";").map((s) => s.replace(/\s+/g, " ").trim()).filter(Boolean)) await db.exec(stmt);
  }
}, 120_000);
afterAll(async () => { await mf?.dispose(); });

describe("online Job Agent", () => {
  it("needs the password", async () => {
    let r = await req("/");
    expect(await r.text()).toContain('name="password"');
    expect((await req("/api/status")).status).toBe(401);
    r = await mf.dispatchFetch(base + "/login", { method: "POST", body: new URLSearchParams({ password: "wrong" }), redirect: "manual" } as any);
    expect(r.status).toBe(401);
    r = await mf.dispatchFetch(base + "/login", { method: "POST", body: new URLSearchParams({ password: "correct horse battery" }), redirect: "manual" } as any);
    expect(r.status).toBe(303);
    cookie = (r.headers.get("Set-Cookie") || "").split(";")[0];
    const page = await (await req("/")).text();
    token = /"token":"([^"]+)"/.exec(page)![1];
    expect(page).toContain("JOB_AGENT_CLOUD");
    const saved = token; token = "bad";
    expect((await req("/api/status")).status).toBe(403);   // API calls need the page's token
    token = saved;
  });

  it("serves the job sites catalogue and keeps the choice", async () => {
    const cat = await (await req("/api/job_sites")).json<any>();
    expect(Object.keys(cat.countries)).toContain("SE");
    await req("/api/search_config", { json: { job_sites: { countries: ["SE"], skip: [], custom: [] } } });
    expect((await (await req("/api/search_config")).json<any>()).job_sites.countries).toEqual(["SE"]);
  });

  it("searches like the local engine", async () => {
    await req("/api/search_config", { json: {
      keywords: ["FPGA engineer", "ASIC design engineer", "embedded hardware engineer", "ASIC verification engineer"],
      locations: [{ name: "Västerås", country: "SE" }, { name: "Uppsala", country: "SE" }, { name: "Oslo", country: "NO", aliases: ["Bærum"] }] } });
    await req("/api/employers", { json: { employers: [
      { name: "Example AI", urls: ["https://jobs.ashbyhq.com/exampleai"] }, { name: "Example GH", urls: ["https://boards.greenhouse.io/examplegh"] },
      { name: "Example Lever", urls: ["https://jobs.lever.co/examplelever"] }, { name: "Example WD", urls: ["https://examplewd.wd3.myworkdayjobs.com/en-US/External"] },
      { name: "JSONLD Corp", urls: ["https://jsonld.example/careers"] }, { name: "Links Corp", urls: ["https://links.example/careers"] },
      { name: "Indeed Only", urls: ["indeed:Indeed Only"] }] } });
    expect((await req("/api/run", { json: {} })).status).toBe(200);
    let job: any;
    for (let i = 0; i < 80; i++) { job = (await (await req("/api/job")).json<any>()).job; if (job.done) break; }
    expect(job.done).toBe(true);
    const { postings } = await (await req("/api/postings")).json<any>();
    if (process.env.DEBUG_WORKER) {
      const db = await mf.getD1Database("DB");
      console.log(JSON.stringify((await db.prepare("SELECT line FROM log").all()).results, null, 1));
      console.log(JSON.stringify((await db.prepare("SELECT kind, state, result FROM tasks").all()).results));
      console.log(calls.slice(0, 40).join("\n"));
    }
    const by = Object.fromEntries(postings.map((p: any) => [p.title, p]));
    for (const t of ["Hardware Developer FPGA", "Digital Design Engineer, ASIC", "FPGA Engineer", "Embedded Hardware Engineer",
                     "ASIC Design Engineer", "Hardware Engineer, FPGA", "FPGA Developer"]) expect(by[t], t).toBeTruthy();
    for (const t of ["Senior FPGA Engineer", "Säljare", "Marketing Manager"]) expect(by[t], t).toBeFalsy();
    expect(by["ASIC Design Engineer"].skills).toContain("SystemVerilog");          // Workday details were fetched
    expect(by["FPGA Developer"].status).toBe("New");                                // link lead confirmed from its page
    expect(by["FPGA Developer"].deadline).toBe("2026-12-01");
    expect(calls.some((u) => u.includes("indeed"))).toBe(false);
    // a second search adds nothing
    await req("/api/run", { json: {} });
    for (let i = 0; i < 80; i++) { job = (await (await req("/api/job")).json<any>()).job; if (job.done) break; }
    expect((await (await req("/api/postings")).json<any>()).postings.length).toBe(postings.length);
  }, 120_000);

  it("adds a posting from a link", async () => {
    await req("/api/fetch", { json: { url: "https://plain.example/jobs/1", employer: "Plain AB", title: "Embedded Engineer" } });
    for (let i = 0; i < 10; i++) if ((await (await req("/api/job")).json<any>()).job.done) break;
    const p = (await (await req("/api/postings")).json<any>()).postings.find((x: any) => x.employer === "Plain AB");
    expect(p?.deadline).toBe("2026-11-30");
  });

  it("decisions and the sync API", async () => {
    const { postings } = await (await req("/api/postings")).json<any>();
    const key = postings.find((p: any) => p.title === "FPGA Engineer").key;
    expect((await req("/api/decision", { json: { key, decision: "accepted" } })).status).toBe(200);
    const bad = await mf.dispatchFetch(base + "/api/sync/export", { headers: { Authorization: "Bearer nope" } });
    expect(bad.status).toBe(401);
    const ex = await (await mf.dispatchFetch(base + "/api/sync/export", { headers: { Authorization: "Bearer sync-secret-123" } })).json<any>();
    expect(ex.decisions[key].decision).toBe("accepted");
    expect(ex.postings.find((p: any) => p.key === key).description).toBeTruthy();
    // a newer decision from the computer wins
    const other = postings.find((p: any) => p.title === "Embedded Hardware Engineer").key;
    const r = await mf.dispatchFetch(base + "/api/sync/decisions", { method: "POST", headers: { Authorization: "Bearer sync-secret-123", "Content-Type": "application/json" },
      body: JSON.stringify({ decisions: { [other]: { decision: "rejected", reasons: ["Location too far / not commutable"], ts: "2099-01-01T00:00:00" } } }) });
    expect((await r.json<any>()).applied).toBe(1);
    const after = (await (await req("/api/postings")).json<any>()).postings.find((p: any) => p.key === other);
    expect(after.status).toMatch(/^Rejected: Location/);
  });

  it("the daily cron starts and works a run", async () => {
    const db = await mf.getD1Database("DB");
    await db.exec("DELETE FROM runs");
    const w = await mf.getWorker();
    await w.scheduled({ cron: "*/2 * * * *" });
    const run = await db.prepare("SELECT mode FROM runs ORDER BY id DESC LIMIT 1").first<any>();
    expect(["weekly", "daily"]).toContain(run.mode);
  });
});
