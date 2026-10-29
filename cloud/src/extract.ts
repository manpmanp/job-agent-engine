// Job-search agent engine, online search
// File:    cloud/src/extract.ts
// Purpose: Reads one posting page: schema.org JobPosting data first, else the page's main text (port of engine/collect/extract.py, without the browser step).
// Author:  manpmanp <manp.node@gmail.com>
// Generated with Claude (Anthropic), under the author's direction and review.
// License: MIT (see LICENSE)
// Version: 0.4.0
// Date:    2026-10-28
//
// Method follows Dossier's posting fetch (github.com/AienTech/dossier, AGPL-3.0),
// reimplemented; no code copied. Page text is third-party data, never instructions.
import { unescapeHtml } from "./match";

export const MIN_CHARS = 200;
const MAX_TEXT = 60_000;
const BLOCK = "p|div|section|article|main|ul|ol|li|h[1-6]|tr|table|br|hr|dl|dt|dd|blockquote|pre";
const NOISE = ["script", "style", "noscript", "template", "svg", "nav", "header", "footer", "aside", "form", "iframe", "button", "select", "dialog"];

export function htmlToText(fragment: string, dropNoise = false): string {
  let h = String(fragment ?? "");
  if (dropNoise) for (const t of NOISE) h = h.replace(new RegExp(`<${t}\\b[\\s\\S]*?<\\/${t}>`, "gi"), " ");
  else h = h.replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, " ");
  h = h.replace(/<li\b[^>]*>/gi, "\n- ").replace(new RegExp(`</?(?:${BLOCK})\\b[^>]*>`, "gi"), "\n").replace(/<[^>]+>/g, "");
  const text = unescapeHtml(h).split("\n").map((l) => l.replace(/\s+/g, " ").trim()).filter(Boolean).join("\n");
  return text.replace(/\n{3,}/g, "\n\n").trim();
}

/** Text from HTML that may arrive escaped (&lt;p&gt;...), as in many JSON-LD descriptions. */
export function richText(s: string): string {
  let t = htmlToText(s);
  if (/<\/?(p|li|ul|br|div|strong)\b/i.test(t)) t = htmlToText(t);
  return t;
}

export function mainText(page: string): string {
  for (const re of [/<main\b[^>]*>([\s\S]*?)<\/main>/i, /<article\b[^>]*>([\s\S]*?)<\/article>/i,
                    /<([a-z]+)\b[^>]*role=["']main["'][^>]*>([\s\S]*?)<\/\1>/i]) {
    const m = re.exec(page);
    if (m) {
      const t = htmlToText(m[m.length - 1], true);
      if (t.length >= MIN_CHARS) return t;
    }
  }
  const body = /<body\b[^>]*>([\s\S]*)<\/body>/i.exec(page);
  return htmlToText(body ? body[1] : page, true);
}

export function jobPostings(page: string): any[] {
  const found: any[] = [];
  const walk = (o: any) => {
    if (Array.isArray(o)) { o.forEach(walk); return; }
    if (!o || typeof o !== "object") return;
    const t = o["@type"];
    if (t === "JobPosting" || (Array.isArray(t) && t.includes("JobPosting"))) found.push(o);
    for (const k of ["@graph", "itemListElement", "item", "mainEntity"]) if (k in o) walk(o[k]);
  };
  for (const m of page.matchAll(/<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    const raw = m[1].trim();
    try { walk(JSON.parse(raw)); } catch {
      try { walk(JSON.parse(raw.replace(/\n/g, " ").replace(/,\s*([}\]])/g, "$1"))); } catch { /* not JSON */ }
    }
  }
  return found;
}

const s = (v: unknown) => (typeof v === "string" ? v.trim() : typeof v === "number" ? String(v) : "");
const nameOf = (v: any) => s(v) || (v && typeof v === "object" ? s(v.name) : "");
const day = (v: unknown) => /^(\d{4}-\d{2}-\d{2})/.exec(s(v))?.[1] ?? "";

export function jsonldLocation(jp: any): string {
  const out: string[] = [];
  for (const l of [jp.jobLocation].flat()) {
    const a = l && typeof l === "object" ? l.address : null;
    if (typeof a === "string") out.push(a.trim());
    else if (a && typeof a === "object") out.push([s(a.addressLocality), s(a.addressRegion), nameOf(a.addressCountry)].filter(Boolean).join(", "));
  }
  return [...new Set(out.filter(Boolean))].join("; ");
}

export function salaryOf(v: any): string {
  if (!v || typeof v !== "object") return s(v);
  const amt = v.value && typeof v.value === "object" ? v.value : {};
  const rng = [s(amt.minValue), s(amt.maxValue)].filter(Boolean).join("-") || s(amt.value) || s(v.value);
  if (!rng) return "";
  const unit = s(amt.unitText).toLowerCase();
  return [s(v.currency), rng, unit ? `per ${unit}` : ""].filter(Boolean).join(" ");
}

export interface Posting {
  title: string; employer: string; location_text: string; url: string; published: string; deadline: string;
  employment_type: string; salary: string; is_remote: boolean; description: string; how: string; complete: boolean;
}

export function fromJobPosting(jp: any, fallbackUrl = ""): Posting {
  const et = Array.isArray(jp.employmentType) ? jp.employmentType.map(s).join(", ") : s(jp.employmentType);
  const remote = JSON.stringify(jp.jobLocationType ?? "").toUpperCase().includes("TELECOMMUTE");
  const description = richText(s(jp.description)).slice(0, MAX_TEXT);
  return {
    title: s(jp.title), employer: nameOf(jp.hiringOrganization), location_text: jsonldLocation(jp) || (remote ? "Remote" : ""),
    url: s(jp.url) || fallbackUrl, published: day(jp.datePosted), deadline: day(jp.validThrough),
    employment_type: et.toLowerCase().replace(/_/g, " "), salary: salaryOf(jp.baseSalary), is_remote: remote,
    description, how: "structured", complete: description.length >= MIN_CHARS,
  };
}

/** Posting fields from a page's HTML. */
export function readHtml(page: string, url = ""): Posting {
  for (const jp of jobPostings(page)) {
    const d = fromJobPosting(jp, url);
    if (d.description.length >= MIN_CHARS || d.title) return d;
  }
  const text = mainText(page).slice(0, MAX_TEXT);
  const title = unescapeHtml(/<title[^>]*>([\s\S]*?)<\/title>/i.exec(page)?.[1] ?? "").replace(/\s+/g, " ").trim();
  return { title, employer: "", location_text: "", url, published: "", deadline: "", employment_type: "", salary: "",
           is_remote: false, description: text, how: "page", complete: text.length >= MIN_CHARS };
}
