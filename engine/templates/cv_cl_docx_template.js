// Job-search agent engine
// File:    engine/templates/cv_cl_docx_template.js
// Purpose: Styled building blocks for CV and cover-letter .docx files.
// Author:  manpmanp <manp.node@gmail.com>
// Generated with Claude (Anthropic), under the author's direction and review.
// License: MIT (see LICENSE)
// Version: 0.2.0
// Date:    2026-10-28

// Building blocks for CV and cover-letter .docx files (docx npm module).
// All visual choices come from a style object (inputs/document_style.json,
// merged over the defaults below), so the same code serves any candidate.
const {
  Document, Packer, Paragraph, TextRun, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  TabStopType, TabStopPosition,
} = require("docx");

const DEFAULT_STYLE = {
  font: "Calibri",
  banner_color: "1F3864",
  accent_color: "2E74B5",
  secondary_text_color: "595959",
  body_text_color: "222222",
  page_size: "A4",
};

const PAGE_SIZES = {
  A4: { width: 11906, height: 16838 },
  Letter: { width: 12240, height: 15840 },
};

function noBorders() {
  const n = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  return { top: n, bottom: n, left: n, right: n };
}

function makeTemplate(userStyle = {}) {
  const S = { ...DEFAULT_STYLE, ...userStyle };
  const FONT = S.font, NAVY = S.banner_color, ACCENT = S.accent_color;
  const GRAY = S.secondary_text_color, BLACK = S.body_text_color;
  const PAGE = {
    size: PAGE_SIZES[S.page_size] || PAGE_SIZES.A4,
    margin: { top: 500, bottom: 600, left: 850, right: 850 },
  };

  function bannerParagraphs({ name, title, subtitle, contact }) {
    const lines = [
      new Paragraph({ spacing: { before: 200, after: 40 },
        children: [new TextRun({ text: name || "", bold: true, color: "FFFFFF", size: 44, font: FONT })] }),
      new Paragraph({ spacing: { after: 60 },
        children: [new TextRun({ text: title || "", color: "FFFFFF", size: 24, font: FONT })] }),
    ];
    if (subtitle) {
      lines.push(new Paragraph({ spacing: { after: 60 },
        children: [new TextRun({ text: subtitle, color: "FFFFFF", size: 18, font: FONT })] }));
    }
    lines.push(new Paragraph({ spacing: { after: 200 },
      children: [new TextRun({ text: contact || "", color: "FFFFFF", size: 18, font: FONT })] }));
    return lines;
  }

  function bannerTable(opts) {
    const n = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
    return new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      borders: { top: n, bottom: n, left: n, right: n, insideHorizontal: n, insideVertical: n },
      rows: [new TableRow({ children: [new TableCell({
        width: { size: 100, type: WidthType.PERCENTAGE },
        shading: { type: ShadingType.CLEAR, color: "auto", fill: NAVY },
        margins: { top: 160, bottom: 160, left: 0, right: 0 },
        children: bannerParagraphs(opts),
      })] })],
    });
  }

  function sectionHeader(text, opts = {}) {
    return new Paragraph({
      pageBreakBefore: !!opts.pageBreakBefore,
      spacing: { before: 260, after: 100 },
      border: { bottom: { color: ACCENT, space: 4, style: BorderStyle.SINGLE, size: 6 } },
      children: [new TextRun({ text: String(text).toUpperCase(), bold: true, color: ACCENT, size: 20, font: FONT, characterSpacing: 20 })],
    });
  }

  function bodyParagraph(text, opts = {}) {
    return new Paragraph({
      spacing: { after: opts.after ?? 120, line: 264 },
      alignment: opts.align || AlignmentType.LEFT,
      children: [new TextRun({ text, size: opts.size || 20, font: FONT, color: opts.color || BLACK, italics: !!opts.italics, bold: !!opts.bold })],
    });
  }

  function bulletParagraph(text) {
    return new Paragraph({ spacing: { after: 130, line: 264 }, bullet: { level: 0 },
      children: [new TextRun({ text, size: 20, font: FONT, color: BLACK })] });
  }

  function jobHeaderRow(titleLeft, dateRight) {
    return new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
      spacing: { before: 260, after: 30 },
      children: [
        new TextRun({ text: titleLeft || "", bold: true, size: 20, font: FONT, color: BLACK }),
        new TextRun({ text: `\t${dateRight || ""}`, size: 20, font: FONT, color: GRAY }),
      ],
    });
  }

  function companyLine(text) {
    return new Paragraph({ spacing: { after: 140 },
      children: [new TextRun({ text: text || "", italics: true, size: 19, font: FONT, color: GRAY })] });
  }

  function skillTable(rows) {
    return new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      columnWidths: [2200, 7800],
      borders: noBorders(),
      rows: rows.map(([l, v]) => new TableRow({ children: [
        new TableCell({ width: { size: 22, type: WidthType.PERCENTAGE }, margins: { top: 40, bottom: 40, left: 0, right: 120 }, borders: noBorders(),
          children: [new Paragraph({ children: [new TextRun({ text: l || "", bold: true, size: 19, font: FONT, color: BLACK })] })] }),
        new TableCell({ width: { size: 78, type: WidthType.PERCENTAGE }, margins: { top: 40, bottom: 40, left: 0, right: 0 }, borders: noBorders(),
          children: [new Paragraph({ children: [new TextRun({ text: v || "", size: 19, font: FONT, color: BLACK })] })] }),
      ] })),
    });
  }

  return { PAGE, FONT, NAVY, ACCENT, GRAY, BLACK, bannerTable, sectionHeader, bodyParagraph,
           bulletParagraph, jobHeaderRow, companyLine, skillTable };
}

module.exports = {
  Document, Packer, Paragraph, TextRun, AlignmentType, makeTemplate, DEFAULT_STYLE,
  ...makeTemplate(),
};
