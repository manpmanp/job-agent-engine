// Job-search agent engine, online search
// File:    cloud/src/match.ts
// Purpose: Matching rules, ported one to one from engine/collect/match.py (shared tests in tests/shared/ keep them in step).
// Author:  manpmanp <manp.node@gmail.com>
// Generated with Claude (Anthropic), under the author's direction and review.
// License: MIT (see LICENSE)
// Version: 0.4.0
// Date:    2026-10-28

const W = "[\\p{L}\\p{N}_]"; // Python's \w on unicode text

export const GENERIC_TOKENS = new Set([
  "engineer", "engineers", "developer", "developers", "designer", "specialist", "expert",
  "utvecklare", "ingenjor", "ingenjör", "konstruktor", "konstruktör", "senior", "junior", "lead",
  "of", "and", "the", "for", "och", "i", "in",
]);

const COUNTRY_NAMES: Record<string, string[]> = {
  SE: ["sweden", "sverige"], DK: ["denmark", "danmark"], NO: ["norway", "norge"],
  FI: ["finland", "suomi"], DE: ["germany", "deutschland"], NL: ["netherlands", "nederland"],
  IS: ["iceland"], AT: ["austria", "osterreich"], CH: ["switzerland", "schweiz", "suisse"],
  GB: ["united kingdom", "uk", "england", "scotland", "wales"], IE: ["ireland", "eire"],
  FR: ["france"], BE: ["belgium", "belgie", "belgique"], ES: ["spain", "espana"], IT: ["italy", "italia"],
  PL: ["poland", "polska"], US: ["united states", "usa"], CA: ["canada"], AU: ["australia"],
};

const SENIORITY_PATTERNS: [string, RegExp][] = [
  ["Manager", /\b(manager|head of|director|chef|avdelningschef|gruppchef)\b/],
  ["Principal", /\bprincipal\b/],
  ["Staff", /\bstaff\b/],
  ["Lead", /\b(lead|tech lead|team lead)\b/],
  ["Architect", /\barchitect\b/],
  ["Senior", /\b(senior|sr\.?)\b/],
  ["Graduate", /\b(graduate|new grad|trainee|intern|internship|thesis|exjobb|praktik)\b/],
  ["Entry", /\b(junior|jr\.?|entry[- ]level)\b/],
];

const ACADEMIA_HINTS: [string, RegExp][] = [
  ["Academia - Postdoc/Researcher", /\b(postdoc|post-doc|postdoctoral|researcher|forskare|research fellow)\b/],
  ["Academia - Lecturer/Assistant Professor", /\b(lecturer|lektor|assistant professor|biträdande lektor|professor)\b/],
  ["Academia - Research Engineer/Assistant", /\b(research engineer|forskningsingenjör|research assistant|forskningsassistent)\b/],
];

// unicode-mode regexes reject needless escapes such as \- outside a class
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Lowercase, strip accents (Västerås -> vasteras), collapse whitespace. */
export function fold(s: unknown): string {
  return String(s ?? "").normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, " ").trim();
}

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", ndash: "–", mdash: "—", hellip: "…", rsquo: "’", lsquo: "‘", rdquo: "”", ldquo: "“", bull: "•" };
export function unescapeHtml(s: string): string {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e: string) => {
    if (e[0] === "#") {
      const n = e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return Number.isFinite(n) ? String.fromCodePoint(n) : m;
    }
    return ENTITIES[e.toLowerCase()] ?? m;
  });
}

export function stripHtml(s: unknown): string {
  let t = String(s ?? "").replace(/<(script|style)[\s\S]*?<\/\1>/gi, " ");
  t = t.replace(/<br\s*\/?>|<\/p>|<\/li>|<\/h\d>/gi, "\n").replace(/<[^>]+>/g, " ");
  return unescapeHtml(unescapeHtml(t)).replace(/[ \t]+/g, " ").trim();
}

export function keywordTokens(keyword: string): string[] {
  const toks = fold(keyword).split(/[^\p{L}\p{N}_+#\/.\-]+/u).filter(Boolean);
  const core = toks.filter((t) => !GENERIC_TOKENS.has(t));
  return core.length ? core : toks;
}

function has(token: string, text: string): boolean {
  return new RegExp(`(?<!${W})${escapeRe(token)}(?!${W})`, "u").test(text);
}

// A keyword word in a title, also in a near form (see match.py _has_word).
function hasWord(token: string, text: string): boolean {
  if (has(token, text)) return true;
  if (token.length < 5 || !/^[\p{L}\p{N}_]+$/u.test(token)) return false;
  for (const w of text.match(/[\p{L}\p{N}_]+/gu) ?? []) {
    if (w.length >= 5 && Math.abs(w.length - token.length) <= 3 && (w.startsWith(token) || token.startsWith(w))) return true;
  }
  return false;
}

function hasPhrase(tokens: string[], text: string): boolean {
  return new RegExp(`(?<!${W})${tokens.map(escapeRe).join("[\\s\\-]+")}(?!${W})`, "u").test(text);
}

export type Where = "title" | "description" | null;

export function matchKeywords(title: unknown, description: unknown, keywords: string[],
                              scope = "title_or_description", excludeTerms: string[] = []): [string[], Where] {
  const t = fold(title), d = fold(description);
  for (const ex of excludeTerms || []) if (ex && has(fold(ex), t)) return [[], null];
  const inTitle: string[] = [], inDesc: string[] = [];
  const titleRole = /(design|develop|engineer|ingenj|utveckl|konstrukt|architect|research)/.test(t);
  for (const kw of keywords) {
    const toks = keywordTokens(kw);
    if (!toks.length) continue;
    if (toks.every((x) => hasWord(x, t))) inTitle.push(kw);
    else if (scope === "title_or_description" && titleRole && hasPhrase(toks, d)) inDesc.push(kw);
  }
  if (inTitle.length) return [inTitle, "title"];
  if (inDesc.length) return [inDesc, "description"];
  return [[], null];
}

export type Location = string | { name: string; country?: string; aliases?: string[]; priority?: number };

export function locationNames(loc: Location): string[] {
  const names = typeof loc === "string" ? [fold(loc)] : [loc.name ?? "", ...(loc.aliases ?? [])].filter(Boolean).map(fold);
  for (const n of [...names]) {
    for (const alts of Object.values(COUNTRY_NAMES)) if (alts.includes(n)) for (const a of alts) if (!names.includes(a)) names.push(a);
  }
  return names;
}

function countriesOf(locations: Location[]): Set<string> {
  const out = new Set<string>();
  for (const l of locations) {
    if (typeof l === "object" && l.country) {
      for (const c of COUNTRY_NAMES[String(l.country).toUpperCase()] ?? [fold(l.country)]) out.add(c);
    }
  }
  return out;
}

export function matchLocation(locationText: unknown, locations: Location[], remoteOk = true, isRemote = false): string | null {
  const lt = fold(locationText);
  for (const l of locations) {
    for (const n of locationNames(l)) if (n && has(n, lt)) return typeof l === "string" ? l : l.name;
  }
  if (remoteOk && (isRemote || /\bremote\b|\bdistans\b/.test(lt))) {
    const cs = countriesOf(locations);
    if (!cs.size || [...cs].some((c) => lt.includes(c)) || /\b(europe|eu|emea|nordic|nordics|scandinavia)\b/.test(lt)) return "remote";
  }
  return null;
}

const JUNIOR_WELCOME = [
  /\bjunior\b[^.\n]{0,30}\b(?:and|or|as well as|&)\b[^.\n]{0,20}\bsenior\b/,
  /\bsenior\b[^.\n]{0,20}\b(?:and|or|as well as|&)\b[^.\n]{0,30}\bjunior\b/,
  /\bwelcome[sd]?\b[^.\n]{0,20}\bjunior\b/,
  /\ball (?:experience|seniority|career) levels\b/,
  /\bjunior(?:a)? (?:och|eller) senior(?:a)?\b/,
  /\bsenior(?:a)? (?:och|eller) junior(?:a)?\b/,
];
export const welcomesJunior = (description: unknown) => JUNIOR_WELCOME.some((p) => p.test(fold(description)));

export function seniority(title: unknown): string {
  const t = fold(title);
  for (const [label, pat] of SENIORITY_PATTERNS) if (pat.test(t)) return label;
  return "Not stated";
}

export function arrangement(...texts: unknown[]): string {
  const t = fold(texts.map((x) => String(x ?? "")).join(" "));
  if (/\b(fully remote|remote[- ]first|100% remote|distansarbete|helt pa distans)\b/.test(t) || /^remote\b/.test(t)) return "Remote";
  if (/\bhybrid\b/.test(t)) return "Hybrid";
  if (/\b(on[- ]?site|onsite|arbete pa plats|in office)\b/.test(t)) return "Onsite";
  if (/\bremote\b/.test(t)) return "Remote";
  return "Not stated";
}

export function category(title: unknown, description: unknown, categories: string[], rules: Record<string, string[]> = {}): string {
  const t = fold(title) + " " + fold(description).slice(0, 2000);
  for (const [cat, terms] of Object.entries(rules || {})) if (terms.some((x) => has(fold(x), t))) return cat;
  for (const [cat, pat] of ACADEMIA_HINTS) if (categories.includes(cat) && pat.test(fold(title))) return cat;
  for (const cat of categories) if (cat.toLowerCase().startsWith("industry")) return cat;
  return categories.includes("Other") || !categories.length ? "Other" : categories[0];
}

export function skillsSummary(description: unknown, vocabulary: string[], limit = 10): string {
  const d = fold(description), raw = String(description ?? "");
  const found: string[] = [];
  for (const term of vocabulary) {
    const ft = fold(term);
    if (!ft || found.includes(term)) continue;
    const exact = term.length <= 2 || (term === term.toUpperCase() && /[A-Z]/.test(term) && term.length <= 5);
    const hit = exact ? new RegExp(`(?<![\\p{L}\\p{N}_+#-])${escapeRe(term)}(?![\\p{L}\\p{N}_+#-])`, "u").test(raw) : has(ft, d);
    if (hit) found.push(term);
    if (found.length >= limit) break;
  }
  return found.join(", ");
}

const COMPANY_SUFFIXES = /\b(aktiebolag|ab|publ|inc|incorporated|ltd|limited|llc|plc|gmbh|ag|a\/s|as|aps|oy|oyj|bv|nv|sa|sas|srl|spa|corp|corporation|co|company|group|sverige|sweden|danmark|denmark|norge|norway)\b/g;

export function normEmployer(employer: unknown): string {
  return fold(employer).replace(/[()]/g, " ").replace(COMPANY_SUFFIXES, " ").replace(/[^a-z0-9]+/g, "");
}

export function normKey(employer: unknown, title: unknown): string {
  return normEmployer(employer).slice(0, 40) + "|" + fold(title).replace(/[^a-z0-9]+/g, "");
}

const DEADLINE_TEXT = /(?:posting end date|application deadline|last (?:day|date) to apply|last application date|apply (?:no later than|by)|sista ans[oö]kningsdag(?:en)?|sista dag (?:att|f[oö]r att) s[oö]ka|ans[oö]k senast)\s*(?:is|[aä]r)?\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})/i;

/** The deadline the posting text itself states, or "". */
export const statedDeadline = (text: unknown) => DEADLINE_TEXT.exec(String(text ?? ""))?.[1] ?? "";

/** 'YYYY-MM-DD' from ISO-ish text or epoch seconds/ms, else "". */
export function isoDay(s: unknown): string {
  if (s === null || s === undefined || s === "") return "";
  if (typeof s === "number") return new Date(s > 1e11 ? s : s * 1000).toISOString().slice(0, 10);
  return /^(\d{4}-\d{2}-\d{2})/.exec(String(s))?.[1] ?? "";
}

const SENIOR_DEFAULT = { flag_as_too_senior: ["Senior", "Staff", "Lead", "Principal", "Architect", "Manager"], flag_as_too_junior: ["Graduate", "Entry"], preferred: ["Experienced", "Mid"] };
export function seniorityBucket(value: unknown, cfg: Record<string, string[]> = {}): "senior" | "junior" | "good" | "other" {
  const c = { ...SENIOR_DEFAULT, ...Object.fromEntries(Object.entries(cfg || {}).filter(([, v]) => Array.isArray(v) && v.length)) } as typeof SENIOR_DEFAULT;
  const v = String(value ?? "");
  if (c.flag_as_too_senior.some((k) => v.includes(k))) return "senior";
  if (c.flag_as_too_junior.some((k) => v.includes(k))) return "junior";
  if (c.preferred.some((k) => v.includes(k))) return "good";
  return "other";
}
