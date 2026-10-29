// Runs tests/shared/match_cases.json, the same cases the Python engine runs.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import * as m from "../src/match";

const c = JSON.parse(readFileSync(new URL("../../tests/shared/match_cases.json", import.meta.url), "utf8"));

describe("shared cases with the Python engine", () => {
  it("keyword tokens", () => { for (const [kw, toks] of c.keyword_tokens) expect(m.keywordTokens(kw), kw).toEqual(toks); });
  it("keyword matching", () => {
    for (const x of c.match_keywords) expect(m.matchKeywords(x.title, x.description, x.keywords, x.scope, x.exclude ?? [])[1], JSON.stringify(x)).toBe(x.where);
  });
  it("locations", () => { for (const x of c.match_location) expect(m.matchLocation(x.text, x.locations), x.text).toBe(x.expect); });
  it("seniority", () => { for (const [t, w] of c.seniority) expect(m.seniority(t), t).toBe(w); });
  it("arrangement", () => { for (const [t, w] of c.arrangement) expect(m.arrangement(t), t).toBe(w); });
  it("stated deadline", () => { for (const [t, w] of c.stated_deadline) expect(m.statedDeadline(t), t).toBe(w); });
  it("welcomes junior", () => { for (const [t, w] of c.welcomes_junior) expect(m.welcomesJunior(t), t).toBe(w); });
  it("skills", () => { for (const x of c.skills_summary) expect(m.skillsSummary(x.text, x.vocab), x.text).toBe(x.expect); });
  it("employer names", () => { for (const [e, w] of c.norm_employer) expect(m.normEmployer(e), e).toBe(w); });
});
