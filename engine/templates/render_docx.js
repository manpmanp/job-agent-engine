// Job-search agent engine
// File:    engine/templates/render_docx.js
// Purpose: Renders a JSON document spec to .docx.
// Author:  manpmanp <manp.node@gmail.com>
// Generated with Claude (Anthropic), under the author's direction and review.
// License: MIT (see LICENSE)
// Version: 0.3.0
// Date:    2026-10-28

// Renders a document spec (JSON) to .docx.
//   node render_docx.js <spec.json> <out.docx> [style.json]
//
// Spec format (see docs/document_spec.md):
// {
//   "type": "cv" | "cl",
//   "template_note": "optional grey italic line at the top (used for template documents)",
//   "banner": {"name": "", "title": "", "subtitle": "", "contact": ""},
//   CV:  "sections": [
//          {"heading": "Profile", "paragraphs": ["..."]},
//          {"heading": "Work Experience", "entries": [{"title": "", "dates": "", "org": "", "bullets": [""], "paragraphs": [""]}]},
//          {"heading": "Technical Skills", "table": [["Label", "Value"]]},
//          {"heading": "Education", "page_break_before": false, "entries": [...]},
//          {"heading": "References", "paragraphs": ["References available upon request."]}
//        ]
//   CL:  "date": "", "recipient": ["line", "line"], "salutation": "", "paragraphs": ["..."],
//        "closing": "Kind regards,", "signature": ""
// }
const fs = require("fs");
const path = require("path");
const { Document, Packer, makeTemplate } = require("./cv_cl_docx_template.js");

function main() {
  const [specPath, outPath, stylePath] = process.argv.slice(2);
  if (!specPath || !outPath) {
    console.error("usage: node render_docx.js <spec.json> <out.docx> [style.json]");
    process.exit(2);
  }
  const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
  const style = stylePath && fs.existsSync(stylePath) ? JSON.parse(fs.readFileSync(stylePath, "utf8")) : {};
  const T = makeTemplate(style);
  const children = [];

  children.push(T.bannerTable(spec.banner || {}));
  if (spec.template_note) {
    children.push(T.bodyParagraph(spec.template_note, { italics: true, color: T.GRAY, size: 17, after: 60 }));
  }

  if (spec.type === "cl") {
    children.push(T.bodyParagraph("", { after: 120 }));
    if (spec.date) children.push(T.bodyParagraph(spec.date, { after: 160 }));
    (spec.recipient || []).forEach((l, i, a) => children.push(T.bodyParagraph(l, { after: i === a.length - 1 ? 200 : 0 })));
    if (spec.salutation) children.push(T.bodyParagraph(spec.salutation, { after: 160 }));
    (spec.paragraphs || []).forEach((p) => children.push(T.bodyParagraph(p, { after: 160 })));
    children.push(T.bodyParagraph(spec.closing || "Kind regards,", { after: 60 }));
    children.push(T.bodyParagraph(spec.signature || (spec.banner || {}).name || "", { bold: true }));
  } else {
    for (const sec of spec.sections || []) {
      if (sec.heading) children.push(T.sectionHeader(sec.heading, { pageBreakBefore: !!sec.page_break_before }));
      (sec.paragraphs || []).forEach((p) => children.push(T.bodyParagraph(p)));
      for (const e of sec.entries || []) {
        children.push(T.jobHeaderRow(e.title, e.dates));
        if (e.org) children.push(T.companyLine(e.org));
        (e.paragraphs || []).forEach((p) => children.push(T.bodyParagraph(p)));
        (e.bullets || []).forEach((b) => children.push(T.bulletParagraph(b)));
      }
      if (sec.table && sec.table.length) children.push(T.skillTable(sec.table));
      (sec.bullets || []).forEach((b) => children.push(T.bulletParagraph(b)));
    }
  }

  const doc = new Document({
    styles: { default: { document: { run: { font: T.FONT } } } },
    sections: [{ properties: { page: T.PAGE }, children }],
  });
  Packer.toBuffer(doc).then((buf) => {
    fs.mkdirSync(path.dirname(path.resolve(outPath)), { recursive: true });
    fs.writeFileSync(outPath, buf);
    console.log(`wrote ${outPath}`);
  });
}

main();
