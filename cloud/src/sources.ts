// Job-search agent engine, online search
// File:    cloud/src/sources.ts
// Purpose: Collectors, ported from engine/collect/sources.py. Each call fetches ONE page and returns its candidates plus the next page as a follow-up task, so every run stays within the Free plan's limits.
// Author:  manpmanp <manp.node@gmail.com>
// Generated with Claude (Anthropic), under the author's direction and review.
// License: MIT (see LICENSE)
// Version: 0.4.0
// Date:    2026-10-28
import { Net } from "./http";
import { isoDay, stripHtml, matchKeywords } from "./match";
import { fromJobPosting, jobPostings, readHtml, richText } from "./extract";

export interface Candidate {
  title: string; employer: string; location_text: string; url: string; apply_url: string; published: string;
  deadline: string; description: string; is_remote: boolean; workplace: string; employment_type: string;
  skills: string[]; source: string; lead?: boolean; posted_text?: string;
  detail?: { kind: string; [k: string]: string };   // a follow-up fetch that fills the description
}

export interface Page { candidates: Candidate[]; next?: Record<string, unknown> | null; error?: string | null; tasks?: { kind: string; payload: any }[] }

const cand = (c: Partial<Candidate>): Candidate => ({
  title: "", employer: "", location_text: "", url: "", apply_url: "", published: "", deadline: "", description: "",
  is_remote: false, workplace: "", employment_type: "", skills: [], source: "", ...c,
});
const err = (label: string, r: { error: string | null; status: number }) => `${label}: ${r.error || "HTTP " + r.status}`;
const uniq = (xs: string[]) => [...new Set(xs.filter(Boolean))];

// ---------------------------------------------------------- JobTech / AF
export async function jobtech(net: Net, p: { kw: string; offset?: number }): Promise<Page> {
  const offset = p.offset ?? 0, limit = 25;
  const q = new URLSearchParams({ q: p.kw, limit: String(limit), offset: String(offset) });
  const [r, data] = await net.getJson(`https://jobsearch.api.jobtechdev.se/search?${q}`);
  if (!data) return { candidates: [], error: err(`JobSearch '${p.kw}'`, r) };
  const hits: any[] = data.hits ?? [];
  const out = hits.filter((h) => !h.removed).map((h) => {
    const wa = h.workplace_address ?? {};
    const model = h.workplace_model?.label ?? "";
    return cand({
      title: h.headline ?? "", employer: h.employer?.name ?? "",
      location_text: uniq([wa.city, wa.municipality, wa.region, wa.country]).join(", "),
      url: h.webpage_url ?? "", apply_url: h.application_details?.url ?? "",
      published: isoDay(h.publication_date), deadline: isoDay(h.application_deadline),
      description: h.description?.text ?? "", is_remote: /distans|remote/i.test(model), workplace: model,
      employment_type: h.employment_type?.label ?? "",
      skills: (h.must_have?.skills ?? []).map((s: any) => s.label).filter(Boolean),
      source: "Arbetsformedlingen (JobSearch API)",
    });
  });
  const total = data.total?.value ?? 0;
  const nextOff = offset + limit;
  return { candidates: out, next: nextOff < Math.min(total, 200) && hits.length ? { kw: p.kw, offset: nextOff } : null };
}

export async function jobtechAdStatus(net: Net, id: string): Promise<"live" | "removed" | "unknown"> {
  const [r, data] = await net.getJson(`https://jobsearch.api.jobtechdev.se/ad/${encodeURIComponent(id)}`);
  if (r.status === 404 || r.status === 410) return "removed";
  if (!data) return "unknown";
  return data.removed ? "removed" : "live";
}

// --------------------------------------------------------- ATS detection
export function detectAts(url: string, explicit?: any): [string, Record<string, string>] {
  if (explicit?.type) return [explicit.type, explicit];
  if (!url || /^(indeed|linkedin):/.test(url) || url.includes("linkedin.com") || url.includes("indeed.")) return ["agent_only", {}];
  let u: URL;
  try { u = new URL(url); } catch { return ["agent_only", {}]; }
  const host = u.host.toLowerCase(), parts = u.pathname.split("/").filter(Boolean);
  if (host.endsWith("greenhouse.io") && parts.length) return ["greenhouse", { board: parts[0] }];
  if (host === "jobs.lever.co" && parts.length) return ["lever", { company: parts[0] }];
  if (host === "jobs.ashbyhq.com" && parts.length) return ["ashby", { org: parts[0] }];
  if (host.endsWith("myworkdayjobs.com")) {
    const site = parts.filter((x) => !/^[a-z]{2}-[A-Z]{2}$/.test(x) && !["job", "wday", "cxs"].includes(x));
    if (site.length) return ["workday", { host, tenant: host.split(".")[0], site: site[0] }];
  }
  if ((host === "jobs.smartrecruiters.com" || host === "careers.smartrecruiters.com") && parts.length) return ["smartrecruiters", { company: parts[0] }];
  return ["html", { url }];
}

// Greenhouse: the list without content (small), descriptions per matched job.
export async function greenhouse(net: Net, p: { board: string; employer: string }): Promise<Page> {
  const [r, data] = await net.getJson(`https://boards-api.greenhouse.io/v1/boards/${p.board}/jobs`);
  if (!data) return { candidates: [], error: err(`Greenhouse '${p.board}'`, r) };
  return {
    candidates: (data.jobs ?? []).map((j: any) => {
      const loc = j.location?.name ?? "";
      const locs = uniq([loc, ...(j.offices ?? []).map((o: any) => o.location || o.name || "")]);
      return cand({ title: j.title ?? "", employer: p.employer, location_text: locs.join("; "), url: j.absolute_url ?? "",
                    apply_url: j.absolute_url ?? "", published: isoDay(j.first_published || j.updated_at),
                    is_remote: /remote/i.test(loc), source: "Greenhouse job board",
                    detail: { kind: "greenhouse", board: p.board, id: String(j.id) } });
    }),
  };
}

export async function lever(net: Net, p: { company: string; employer: string; skip?: number }): Promise<Page> {
  const skip = p.skip ?? 0, limit = 40;
  const [r, data] = await net.getJson(`https://api.lever.co/v0/postings/${p.company}?mode=json&limit=${limit}&skip=${skip}`);
  if (!Array.isArray(data)) return { candidates: [], error: err(`Lever '${p.company}'`, r) };
  return {
    candidates: data.map((j: any) => {
      const c = j.categories ?? {};
      return cand({ title: j.text ?? "", employer: p.employer, location_text: uniq(c.allLocations ?? [c.location ?? ""]).join("; "),
                    url: j.hostedUrl ?? "", apply_url: j.applyUrl ?? "", published: isoDay(j.createdAt),
                    description: j.descriptionPlain || stripHtml(j.description), is_remote: String(j.workplaceType ?? "").toLowerCase() === "remote",
                    workplace: String(j.workplaceType ?? ""), employment_type: c.commitment ?? "", source: "Lever job board" });
    }),
    next: data.length === limit && skip < 400 ? { ...p, skip: skip + limit } : null,
  };
}

export async function ashby(net: Net, p: { org: string; employer: string }): Promise<Page> {
  const [r, data] = await net.getJson(`https://api.ashbyhq.com/posting-api/job-board/${p.org}`);
  if (!data) return { candidates: [], error: err(`Ashby '${p.org}'`, r) };
  return {
    candidates: (data.jobs ?? []).filter((j: any) => j.isListed !== false).map((j: any) => cand({
      title: j.title ?? "", employer: p.employer,
      location_text: uniq([j.location ?? "", ...(j.secondaryLocations ?? []).map((s: any) => s.location ?? "")]).join("; "),
      url: j.jobUrl ?? "", apply_url: j.applyUrl ?? "", published: isoDay(j.publishedAt),
      description: j.descriptionPlain || stripHtml(j.descriptionHtml), is_remote: !!j.isRemote, workplace: j.workplaceType ?? "",
      employment_type: j.employmentType ?? "", source: "Ashby job board",
    })),
  };
}

function workdayPosted(s: unknown, today = new Date()): string {
  const t = String(s ?? "").toLowerCase();
  const d = (n: number) => new Date(today.getTime() - n * 86400000).toISOString().slice(0, 10);
  if (t.includes("today")) return d(0);
  if (t.includes("yesterday")) return d(1);
  const m = /(\d+)\+?\s*day/.exec(t);
  return m && !t.includes("+") ? d(Number(m[1])) : "";
}

export async function workday(net: Net, p: { host: string; tenant: string; site: string; employer: string; kw: string; offset?: number }): Promise<Page> {
  const offset = p.offset ?? 0;
  const [r, data] = await net.postJson(`https://${p.host}/wday/cxs/${p.tenant}/${p.site}/jobs`, { appliedFacets: {}, limit: 20, offset, searchText: p.kw });
  if (!data) return { candidates: [], error: err(`Workday '${p.tenant}/${p.site}' '${p.kw}'`, r) };
  const posts: any[] = data.jobPostings ?? [];
  return {
    candidates: posts.filter((j) => j.externalPath).map((j) => cand({
      title: j.title ?? "", employer: p.employer, location_text: j.locationsText ?? "",
      url: `https://${p.host}/${p.site}${j.externalPath}`, apply_url: `https://${p.host}/${p.site}${j.externalPath}`,
      published: workdayPosted(j.postedOn), source: "Workday career site", posted_text: j.postedOn ?? "",
      detail: { kind: "workday", host: p.host, tenant: p.tenant, site: p.site, path: j.externalPath },
    })),
    next: offset + 20 < Math.min(data.total ?? 0, 100) && posts.length ? { ...p, offset: offset + 20 } : null,
  };
}

export async function smartrecruiters(net: Net, p: { company: string; employer: string; offset?: number }): Promise<Page> {
  const offset = p.offset ?? 0;
  const [r, data] = await net.getJson(`https://api.smartrecruiters.com/v1/companies/${p.company}/postings?limit=100&offset=${offset}`);
  if (!data) return { candidates: [], error: err(`SmartRecruiters '${p.company}'`, r) };
  const items: any[] = data.content ?? [];
  return {
    candidates: items.map((j) => {
      const loc = j.location ?? {};
      return cand({ title: j.name ?? "", employer: p.employer, location_text: uniq([loc.city, loc.region, loc.country]).join(", "),
                    url: `https://jobs.smartrecruiters.com/${p.company}/${j.id}`, published: isoDay(j.releasedDate),
                    is_remote: !!loc.remote, source: "SmartRecruiters", detail: { kind: "page" } });
    }),
    next: offset + 100 < Math.min(data.totalFound ?? 0, 500) && items.length ? { ...p, offset: offset + 100 } : null,
  };
}

/** Careers page without a known API: JSON-LD JobPosting data, or keyword-matching links as leads. */
export async function htmlPage(net: Net, p: { url: string; employer: string; keywords: string[] }): Promise<Page> {
  const r = await net.getPage(p.url);
  if (!r.ok) return { candidates: [], error: err(`${p.employer} page`, r) };
  const structured = jobPostings(r.text).map((jp) => {
    const d = fromJobPosting(jp, p.url);
    return cand({ title: d.title, employer: d.employer || p.employer, location_text: d.location_text, url: d.url || p.url,
                  published: d.published, deadline: d.deadline, description: d.description, is_remote: d.is_remote,
                  employment_type: d.employment_type, source: "Career page (structured data)" });
  });
  if (structured.length) return { candidates: structured };
  const seen = new Set<string>(), out: Candidate[] = [];
  for (const m of r.text.matchAll(/<a\b[^>]*href=["']([^"'#]+)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
    const label = stripHtml(m[2]);
    if (!label || label.length > 160 || !matchKeywords(label, "", p.keywords, "title")[0].length) continue;
    let full: string;
    try { full = new URL(m[1], r.url || p.url).toString(); } catch { continue; }
    if (seen.has(full)) continue;
    seen.add(full);
    out.push(cand({ title: label, employer: p.employer, url: full, source: "Career page (link, unconfirmed)", lead: true, detail: { kind: "page" } }));
  }
  return { candidates: out };
}

// ------------------------------------------------------- follow-up fetch
/** Fills a candidate from its detail source. Returns an error string or null. */
export async function fillDetail(net: Net, c: Candidate): Promise<string | null> {
  const d = c.detail;
  if (!d) return null;
  if (d.kind === "workday") {
    const [r, data] = await net.getJson(`https://${d.host}/wday/cxs/${d.tenant}/${d.site}${d.path}`);
    if (!data) return err(`Workday details '${c.title}'`, r);
    const info = data.jobPostingInfo ?? {};
    c.description = stripHtml(info.jobDescription ?? "");
    c.published ||= isoDay(info.startDate || info.postedOn);
    c.deadline ||= isoDay(info.endDate);
    c.workplace = info.remoteType || c.workplace;
    if (info.location && !c.location_text) c.location_text = info.location;
    return null;
  }
  if (d.kind === "greenhouse") {
    const [r, data] = await net.getJson(`https://boards-api.greenhouse.io/v1/boards/${d.board}/jobs/${d.id}`);
    if (!data) return err(`Greenhouse details '${c.title}'`, r);
    c.description = richText(String(data.content ?? ""));
    return null;
  }
  // a posting page (link leads, SmartRecruiters)
  const r = await net.getPage(c.url);
  if (!r.ok) return err(`page '${c.title}'`, r);
  const p = readHtml(r.text, r.url || c.url);
  if (!p.description) return `page '${c.title}': no posting text (probably built in the browser)`;
  c.description = p.description;
  c.location_text ||= p.location_text;
  c.published ||= p.published;
  c.deadline ||= p.deadline;
  c.employment_type ||= p.employment_type;
  if (p.is_remote) c.is_remote = true;
  if (p.how === "structured") {
    c.lead = false;
    if (p.title) c.title = p.title;
    c.source = c.source.startsWith("Career page") ? "Career page (posting page, structured data)" : c.source;
  } else if (p.complete && c.source.startsWith("Career page")) {
    c.source = "Career page (posting page text)";
  }
  return null;
}

// ------------------------------------------------------------ aggregators
const JSEARCH_HOSTS: Record<string, [string, (k: string) => Record<string, string>]> = {
  openwebninja: ["https://api.openwebninja.com/jsearch", (k) => ({ "x-api-key": k })],
  rapidapi: ["https://jsearch.p.rapidapi.com", (k) => ({ "x-rapidapi-key": k, "x-rapidapi-host": "jsearch.p.rapidapi.com" })],
};

export async function jsearch(net: Net, p: { kw: string; place: string; country: string; key: string; host?: string; cursor?: string; pages_left?: number }): Promise<Page> {
  const [base, hdr] = JSEARCH_HOSTS[p.host ?? "openwebninja"] ?? JSEARCH_HOSTS.openwebninja;
  const q = new URLSearchParams({ query: `${p.kw} in ${p.place}`, country: p.country, date_posted: "month" });
  if (p.cursor) q.set("cursor", p.cursor);
  const [r, data] = await net.getJson(`${base}/search-v2?${q}`, hdr(p.key));
  if (!data) return { candidates: [], error: err(`JSearch '${p.kw}' ${p.place}`, r) };
  const seen = new Set<string>(), out: Candidate[] = [];
  for (const j of data.data?.jobs ?? []) {
    if (!j?.job_id || seen.has(j.job_id)) continue;
    seen.add(j.job_id);
    const opts = (j.apply_options ?? []).filter((o: any) => o && typeof o === "object");
    const direct = opts.find((o: any) => o.is_direct && /^https?:/.test(o.apply_link ?? ""));
    const link = direct?.apply_link || [j.job_apply_link, opts[0]?.apply_link, j.job_google_link].find((v) => /^https?:/.test(v ?? "")) || "";
    const place = String(j.job_location ?? "").split("•")[0].trim() || uniq([j.job_city, j.job_state, j.job_country]).join(", ");
    out.push(cand({ title: j.job_title ?? "", employer: j.employer_name ?? "", location_text: place, url: link,
                    published: isoDay(j.job_posted_at_datetime_utc || j.job_posted_at_timestamp), deadline: isoDay(j.job_offer_expiration_datetime_utc),
                    description: String(j.job_description ?? "").slice(0, 60000), is_remote: !!j.job_is_remote,
                    employment_type: String(j.job_employment_type ?? "").toLowerCase(),
                    source: `JSearch (via ${j.job_publisher || "Google for Jobs"}${direct ? ", employer link" : ""})` }));
  }
  const cursor = data.data?.cursor;
  const left = (p.pages_left ?? 1) - 1;
  return { candidates: out, next: cursor && left > 0 ? { ...p, cursor, pages_left: left } : null };
}

const ADZUNA = new Set(["at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "gb", "in", "it", "mx", "nl", "nz", "pl", "sg", "us", "za"]);
export const adzunaCovers = (country: string) => ADZUNA.has(country === "uk" ? "gb" : country);

export async function adzuna(net: Net, p: { kw: string; place: string; country: string; id: string; key: string }): Promise<Page> {
  const country = p.country === "uk" ? "gb" : p.country;
  const q = new URLSearchParams({ app_id: p.id, app_key: p.key, results_per_page: "50", what: p.kw, where: p.place, distance: "50", max_days_old: "30" });
  const [r, data] = await net.getJson(`https://api.adzuna.com/v1/api/jobs/${country}/search/1?${q}`);
  if (!data) return { candidates: [], error: err(`Adzuna '${p.kw}' ${p.place}`, r) };
  return {
    candidates: (data.results ?? []).filter((j: any) => j?.id).map((j: any) => cand({
      title: stripHtml(j.title), employer: j.company?.display_name ?? "", location_text: j.location?.display_name ?? "",
      url: j.redirect_url ?? "", published: isoDay(j.created), description: stripHtml(j.description),
      employment_type: String(j.contract_time ?? ""), source: "Adzuna (description shortened by the source)",
    })),
  };
}

const hnLink = (id: unknown) => `https://news.ycombinator.com/item?id=${id}`;

export function hnTitle(title: string): [string, string, string] {
  let company: string, rest: string;
  let m = /^(.+?)\s*\(\s*YC\s+([A-Z]\d{2})\s*\)\s*(.*)$/i.exec(title);
  if (m) { company = m[1].trim(); rest = m[3].trim(); }
  else {
    m = /^(.+?)\s+(?:is|are)\s+hiring\b(.*)$/i.exec(title);
    [company, rest] = m ? [m[1].trim(), "is hiring" + m[2]] : [title.trim(), ""];
  }
  let role = rest.replace(/^(?:is|are)\s+hiring\b[\s:\-–—]*/i, "").replace(/^(?:an?|for)\s+/i, "").trim();
  role = role.replace(/\s*[(\[].*$/, "").replace(/\s+in\s+[A-Z][^()[\]]*$/, "").trim();
  const places = [...rest.matchAll(/\(([^)]*)\)|\[([^\]]*)\]/g)].map((x) => (x[1] ?? x[2]).trim());
  const inPlace = /\bin\s+([A-Z][^()[\]]*)$/.exec(rest.replace(/\s*[(\[].*$/, ""))?.[1]?.trim();
  if (inPlace) places.unshift(inPlace);
  return [company, role, places.filter(Boolean).join(" / ")];
}

/** YC job posts: the list of ids, then one follow-up task per post. */
export async function ycList(net: Net): Promise<Page> {
  const [r, ids] = await net.getJson<number[]>("https://hacker-news.firebaseio.com/v0/jobstories.json");
  if (!Array.isArray(ids)) return { candidates: [], error: err("YC job posts", r) };
  return { candidates: [], tasks: ids.slice(0, 60).map((id) => ({ kind: "yc_item", payload: { id } })) };
}

export async function ycItem(net: Net, p: { id: number }): Promise<Page> {
  const [, it] = await net.getJson(`https://hacker-news.firebaseio.com/v0/item/${p.id}.json`);
  if (!it || it.type !== "job" || it.dead || it.deleted || !it.title) return { candidates: [] };
  const [company, role, place] = hnTitle(it.title);
  return { candidates: [cand({ title: role || it.title, employer: company, location_text: place,
                               url: /^https?:/.test(it.url ?? "") ? it.url : hnLink(p.id), published: isoDay(it.time),
                               description: richText(it.text ?? ""), is_remote: /\bremote\b/i.test(it.title),
                               source: "YC job post (Hacker News)", lead: !it.text })] };
}

/** 'Ask HN: Who is hiring?': finds this month's thread, then reads its posts in pages. */
export async function hnThread(net: Net, p: { id?: string; from?: number }): Promise<Page> {
  let id = p.id;
  if (!id) {
    const [r, data] = await net.getJson("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=10");
    const hit = (data?.hits ?? []).find((h: any) => /^ask hn: who is hiring\?/i.test(h.title ?? ""));
    if (!hit) return { candidates: [], error: `HN Who is hiring: ${r.error || "no thread found this month"}` };
    id = hit.objectID;
  }
  // the official HN API gives the thread's post ids; posts are read 15 per task
  const [r, story] = await net.getJson(`https://hacker-news.firebaseio.com/v0/item/${id}.json`);
  if (!story) return { candidates: [], error: err("HN Who is hiring", r) };
  const kids: number[] = story.kids ?? [];
  const from = p.from ?? 0;
  const out: Candidate[] = [];
  for (const k of kids.slice(from, from + 15)) {
    const [, post] = await net.getJson(`https://hacker-news.firebaseio.com/v0/item/${k}.json`);
    if (!post?.text || post.dead || post.deleted) continue;
    const text = richText(post.text);
    const parts = text.split("\n")[0].split(/\s+\|\s+|\s+·\s+/).map((x) => x.trim()).filter(Boolean);
    if (parts.length < 2) continue;
    const company = parts[0].replace(/https?:\/\/\S+|\s*\(.*\)\s*$/g, "").replace(/^[\s\-:]+|[\s\-:]+$/g, "");
    const roles = parts.slice(1).filter((x) => /\b(engineer|developer|architect|designer|scientist|researcher|lead|manager|intern|specialist)\b/i.test(x));
    const places = parts.slice(1).filter((x) => !roles.includes(x));
    out.push(cand({ title: roles.join(" / ") || parts[1], employer: company, location_text: places.join("; "), url: hnLink(k),
                    published: isoDay(post.time), description: text.slice(0, 20000),
                    is_remote: places.some((x) => /\bremote\b/i.test(x)), source: "HN Who is hiring" }));
  }
  return { candidates: out, next: from + 15 < Math.min(kids.length, 600) ? { id, from: from + 15 } : null };
}
