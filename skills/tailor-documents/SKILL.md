---
name: tailor-documents
description: Write a tailored CV and cover letter for one accepted job posting from the candidate material in a job-agent home (profile, uploaded CVs/letters, reference files, personal rules), or a template for a hypothetical candidate when there is none. Use for any accepted posting listed by './run.sh tailor pending'.
---

<!--
  Job-search agent engine
  File:    skills/tailor-documents/SKILL.md
  Purpose: Procedure for writing a tailored CV and cover letter for one accepted posting.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.3.0
  Date:    2026-10-28
-->

# Tailor documents for one posting

Input: one posting from the tracker (`./run.sh tailor pending` gives its
key) and the agent home. Output: a CV spec and a cover-letter spec
(`docs/document_spec.md`), rendered with `./run.sh tailor render`, plus a
JD snapshot. Drafts only; nothing is ever sent.

## 0. Pick the mode from `./run.sh status`

- **Template mode** (`tailoring_full` off): run
  `./run.sh tailor template "<URL>||<Title>"`. The engine builds the
  structure and placeholders from the posting's keywords and fills only
  the profile fields that exist. Do not write candidate content yourself in
  this mode. Stop here.
- **Full mode** (`tailoring_full` on): continue below.

## 1. Read the posting

Fetch the full job description, not a snippet. List explicitly: required
and preferred skills, seniority signals, main responsibilities, and
culture or working-style cues. If the description cannot be fully
retrieved, say so and ask the user for the text rather than drafting from
a fragment.

## 2. Read the candidate material, in this order of authority

1. `inputs/tailoring_rules.md`: the candidate's own mandatory rules. They
   override everything below except the no-invention rule.
2. `inputs/references/`: files the candidate marked as authoritative (for
   example a maintained publication list). Re-read them every time; they
   change.
3. `inputs/candidate/profile.json`: the merged profile. Check
   `./run.sh intake conflicts`; for an open conflict use the value in the
   profile and mention the conflict in the report.
4. Uploaded CVs and cover letters in `inputs/candidate/sources/cv/` and
   `.../cl/`: the candidate's proven wording. Prefer the one closest to
   this posting's type and employer.
5. `inputs/characteristics.md` (if present): only for the motivation part
   of the cover letter; see section 5.

**Never invent.** Tailoring means selecting, ordering, emphasizing and
matching the posting's language. It never adds a skill, tool, project,
responsibility, date, title or number that the material does not contain.
If the material is ambiguous about what the candidate personally did, ask
the user instead of choosing the generous or the cautious reading.

## 3. Build every important claim the same way

Requirement, relevance, evidence, ownership, context, fit:

1. What exactly is the employer asking for?
2. Which real experience is the closest match? Closest beats most
   impressive.
3. What did the candidate personally do (versus the team)?
4. What context makes it credible (scale, technology, tools, constraints,
   a verified result)?
5. Why does it transfer to this role? Say it in one sentence.

Rules that follow from this:
- Use verbs that show ownership (designed, implemented, led, validated,
  integrated, supervised, contributed to) and choose the verb that is true
  for the candidate's actual role.
- Adjectives alone are not evidence. Editing test: remove the adjectives;
  if the sentence no longer shows suitability, replace them with what was
  built, measured, delivered or decided.
- Give most space to the most relevant experience; compress or drop the
  rest. Career volume is not relevance.
- Keep one coherent professional identity across CV and cover letter.
- Personal or independent projects are marked as such at first mention in
  every section where they appear, never blended into employment.
- Numbers: cite them only when the material verifies them and the posting
  values them. Research-flavoured postings usually welcome one or two
  results per project; production-engineering postings usually do not want
  research metrics. Never merge figures from different sources into one.
- Publications: exact titles, venues and years from the authoritative
  source; never shortened or paraphrased.
- Mention only the location(s) the candidate is applying for.

## 4. CV

- Sections are chosen per posting, not fixed. A typical industry CV:
  profile, experience, technical skills (two-column table), education,
  languages, references. Research and academic postings add publications,
  research contributions and teaching where the material supports them.
- Mandatory entries named in `tailoring_rules.md` or
  `tailoring_checks.json` are always present.
- Follow `document_market` conventions (default `nordic`: concise, plain,
  one to two pages, matter-of-fact, no boasting, no headline metrics on
  non-research industry roles).
- Keep sections from splitting awkwardly across pages; use
  `page_break_before` on a section only when the rendered PDF shows it is
  needed.

## 5. Cover letter: a motivation letter, not a second CV

Default shape (short letters may combine parts):
1. **Opening:** the role and the strongest real connection to it, then a
   short bridge into the application. No generic enthusiasm first.
2. **Evidence:** the two or three closest experiences, each with the
   candidate's own contribution.
3. **How the candidate works:** one or two real situations that show it.
4. **Context:** scale, stakeholders or constraints, only where it helps.
5. **Motivation:** why this role and employer, tied to the substance of the
   work.
6. **Close:** what the candidate would contribute, concretely.

Do not repeat the same "why this role" framing in consecutive paragraphs.

If `characteristics.md` exists, include at least one sentence that
reflects a characteristic relevant to this posting, tied to a real
situation, worded freshly for this letter. Never quote that file, name it,
or use assessment terminology in the letter.

## 6. Style

- If `document_style.avoid_em_dash` is true (default), no em dash in any
  sentence; ranges such as dates may use an en dash.
- Apply every style rule in `tailoring_rules.md`.

## 7. Render and verify

1. `./run.sh tailor check <spec>` for each spec; fix every problem.
2. `./run.sh tailor render <spec> --posting "<URL>||<Title>"`.
3. `./run.sh tailor jd "<URL>||<Title>" --text <full description file>`.
4. Convert the .docx files to PDF and look at every page: template look,
   spacing between entries, page breaks, nothing cut off.
5. Read both documents once more against sections 2 to 6. Check: nothing
   invented, mandatory entries present, ownership verbs accurate, personal
   projects marked, numbers verified, titles exact, style rules applied.
6. `./run.sh tailor done "<URL>||<Title>"`.

## 8. Report

File names; mode (full or template); what was emphasized and why; which
requirements mapped to which evidence; optional sections included and why;
open profile conflicts; anything that could not be verified (incomplete
description, missing reference file) so the user can check it.
