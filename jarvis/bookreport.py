#!/usr/bin/env python3
"""
Jarvis's Book Report — professional, chapter-by-chapter expert breakdown.

Give it a book (PDF is best — real page numbers; also .txt/.md/.docx) and
Jarvis produces a professionally formatted study report (HTML + PDF) in
~/Documents/JarvisWork/, built so a reader who has NEVER heard of the book
can discuss it in depth, answer specific questions about the author's
arguments, and apply its frameworks.

Every chapter gets these sections:
  📜 Chapter Overview          💬 Key Quotes (verbatim, page-cited)
  📖 Stories & Case Examples   🎯 Core Teachings
  📊 Frameworks & Tables       📌 Key Terms (chapter glossary)
  ✅ Actionable Lessons        🧠 Mindset & Philosophical Insights
  🔮 Metaphors & Analogies     🤔 Questions for Reflection

Plus: what the book is about + the preface at the start, a full alphabetized
glossary at the end, page references throughout, colored callout boxes, and
an automatic QUOTE AUDIT that verifies every quote verbatim against the book.

Usage:
  python3 bookreport.py <book.pdf>
  python3 bookreport.py <book.pdf> --model qwen2.5:32b

Page numbers are exact for PDFs. For .txt/.docx there are no real pages,
so citations use approximate pages (~300 words each), clearly labeled.
"""

import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jarvis import (  # noqa: E402
    DEFAULT_MODEL,
    LIBRARY_FILE,
    WORK_DIR,
    _extract_text,
    _squash,
    _write_private,
    check_ollama,
    load_library,
    ollama_chat,
    security_check,
    tool_remember_fact,
)

CHUNK_CHARS = 18000  # per model call; safe for an 8B model's context window
APPROX_PAGE_CHARS = 1800  # ~300 words when the format has no real pages

CHAPTER_RE = re.compile(
    r"^\s{0,8}(?:"
    r"(?:chapter|part|book|lecture|section)\s+(?:\d{1,3}|[ivxlcdm]{1,7}|one|two|"
    r"three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b"
    r"|preface|prologue|foreword|introduction|epilogue|conclusion|afterword"
    r"|acknowledg(?:e)?ments?|appendix\s+[a-z0-9]"
    r").{0,70}$",
    re.I | re.M,
)

# ------------------------------------------------------------- book loading


def load_pages(path):
    """Return (pages, exact) — list of page texts, and whether pages are real."""
    if path.lower().endswith(".pdf"):
        out = subprocess.run(["pdftotext", "-layout", path, "-"],
                             capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit("Cannot read PDFs yet — install poppler first:  brew install poppler")
        return out.stdout.split("\f"), True  # pdftotext page separator
    text = _extract_text(path)
    if text.startswith("Cannot"):
        sys.exit(text)
    pages = [text[i:i + APPROX_PAGE_CHARS] for i in range(0, len(text), APPROX_PAGE_CHARS)]
    return pages, False


def mark_pages(pages, start, end, exact):
    """Concatenate pages[start:end] with [p. N] markers the model can cite."""
    tag = "p." if exact else "approx. p."
    return "\n".join(f"[{tag} {i + 1}]\n{pages[i]}" for i in range(start, end))


def find_chapters(pages, exact):
    """Detect chapter headings; return ([(title, start_page, end_page)], structured)."""
    marks = []
    for idx, page in enumerate(pages):
        headings = list(CHAPTER_RE.finditer(page))
        if not headings or len(headings) > 4:  # >4 on one page = table of contents
            continue
        title = _squash(headings[0].group(0)).strip()
        marks.append((idx, title))
    if len(marks) < 2:
        step = max(1, min(15, len(pages) // 8 or 1))
        return [(f"Pages {i + 1}–{min(i + step, len(pages))}", i, min(i + step, len(pages)))
                for i in range(0, len(pages), step)], False
    sections = []
    if marks[0][0] > 0:
        sections.append(("Front matter", 0, marks[0][0]))
    for k, (idx, title) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(pages)
        if end > idx:
            sections.append((title, idx, end))
    return sections, True


# ------------------------------------------------------------- model passes


def ask(model, user, label):
    print(f"  … {label}")
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user}]
    reply = ""
    for chunk, _ in ollama_chat(model, messages, tools=None, stream=True):
        reply += chunk
    return reply.strip()


SYSTEM = """\
You are a professional book analyst creating a deep, chapter-by-chapter
expert breakdown. The reader has NEVER heard of this book; by the end they
must be able to discuss it with someone who read it cover to cover, answer
specific questions about the author's arguments, name the real case studies
and research the author cites, and apply the frameworks in practice.

ABSOLUTE RULES:
1. Use ONLY real content from the text provided: real quotes (verbatim),
   real case examples, real statistics, real stories the author tells.
2. NEVER invent examples to replace the author's. You MAY add a clarifying
   real-world example of your own, but only under the label
   "Supplementary example (not from the book):" and only in addition to —
   never instead of — the author's own material.
3. Quotes must be copied VERBATIM, in "double quotes", each followed by its
   page citation like (p. 12), using the [p. N] markers in the text.
4. Every story, statistic, framework, and definition gets a page reference.
5. Reproduce any charts, tables, or frameworks from the text as markdown
   tables, with their page references.
6. Never invent a quote, page number, name, statistic, or detail. If the
   text is unclear or something is missing, say so plainly.
7. Be thorough — there is no length limit. Cover everything important.
"""

CHAPTER_PROMPT = """\
Produce the expert breakdown of this {what}. Use EXACTLY these section
headers, in this order, each starting with "## ":

## 📜 Chapter Overview
What this chapter covers and where it fits in the book's argument — detailed
enough that the reader genuinely knows the content (2-4 paragraphs).
## 💬 Key Quotes
The most significant passages, verbatim, each with (p. N).
## 📖 Stories & Case Examples
EVERY real story, case study, research finding, and statistic the author
uses, retold with enough detail to cite in a discussion, each with (p. N).
## 🎯 Core Teachings
What the author is actually arguing — every substantive claim (bullets).
## 📊 Frameworks & Tables
Any framework, model, chart, or multi-part structure from the chapter,
reproduced as a markdown table with page refs (or "None in this chapter").
## 📌 Key Terms
Chapter glossary: every specialized term with the author's precise
definition and page ref (or "None introduced").
## ✅ Actionable Lessons
What the reader should actually DO with this knowledge (bullets).
## 🧠 Mindset & Philosophical Insights
The deeper worldview the author conveys here.
## 🔮 Metaphors & Analogies
The author's own metaphors/analogies, with what each one maps to (p. N).
## 🤔 Questions for Reflection
3-5 questions that test genuine understanding of this chapter.

Text of {what} (with page markers):

{text}
"""

MERGE_PROMPT = """\
These are breakdowns of consecutive parts of ONE {what}. Merge them into a
single breakdown with the same "## " section structure (Chapter Overview,
Key Quotes, Stories & Case Examples, Core Teachings, Frameworks & Tables,
Key Terms, Actionable Lessons, Mindset & Philosophical Insights, Metaphors &
Analogies, Questions for Reflection), keeping ALL substance and ALL page
citations. Remove only duplication.

{parts}
"""

OVERVIEW_PROMPT = """\
Using ONLY this opening portion of the book, write two sections with these
exact "## " headers:

## 🏛 What This Book Is About
For a reader who has NEVER heard of it: the book's purpose, central argument
or story, who wrote it and why, intended audience, and how it is structured
(3-4 paragraphs).
## 📝 The Preface & Front Matter
What the author says in the preface/foreword/introduction: why they wrote
it, their approach, promises to the reader — with page citations. If there
is no preface, state that.

Opening text (with page markers):

{text}
"""

GLOSSARY_PROMPT = """\
Below are the "Key Terms" sections from every chapter of one book. Compile
the complete master glossary: alphabetized, one entry per term, the author's
precise definition, chapter and page reference. Merge duplicates. Output as
a markdown table with columns Term | Definition | Where.

{text}
"""


def breakdown_section(model, what, text):
    if len(text) <= CHUNK_CHARS:
        return ask(model, CHAPTER_PROMPT.format(what=what, text=text), f"analyzing {what}")
    parts = []
    for i in range(0, len(text), CHUNK_CHARS):
        parts.append(ask(model,
                         CHAPTER_PROMPT.format(what=f"{what} (part {len(parts) + 1})",
                                               text=text[i:i + CHUNK_CHARS]),
                         f"analyzing {what} — part {len(parts) + 1}"))
    return ask(model, MERGE_PROMPT.format(what=what, parts="\n\n=====\n\n".join(parts)),
               f"merging {what}")


# ------------------------------------------------------------- quote audit

# single-line only and a low char floor: short quoted phrases must still be
# consumed as matches (then skipped by the 5-word rule) or the pairing of
# open/close quote marks drifts and produces false positives
QUOTE_RE = re.compile(r"[\"“]([^\"”“\n]{12,400}?)[\"”]")


def audit_quotes(report, full_text):
    """Verify every quoted passage appears verbatim in the book."""
    corpus = _squash(full_text).lower()
    verified, fabricated = 0, []
    for m in QUOTE_RE.finditer(report):
        quote = _squash(m.group(1)).lower().strip(" .,;:!?")
        if len(quote.split()) < 5:
            continue  # too short to judge
        if quote in corpus:
            verified += 1
        else:
            fabricated.append(m.group(1))
    return verified, fabricated


# ------------------------------------------------------- markdown -> HTML

SECTION_CLASS = {
    "💬": "quotes", "📖": "stories", "🎯": "core", "📊": "frameworks",
    "📌": "terms", "✅": "actions", "🧠": "mindset", "🔮": "metaphors",
    "🤔": "reflect", "📜": "overview", "🏛": "about", "📝": "preface",
}


def _inline(text):
    text = html_lib.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # make page citations visually distinct
    text = re.sub(r"\((approx\. )?pp?\.\s*[\d,\s–-]+\)", r'<span class="pg">\g<0></span>', text)
    return text


BULLET_RE = re.compile(r"^\s*[-*•]\s+")
NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+")


def md_to_html(md):
    """Small markdown converter: headers, bullets, tables, blockquotes, paras."""
    out, lines = [], md.splitlines()
    i, in_ul, in_ol = 0, False, False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    while i < len(lines):
        line = lines[i].rstrip()
        # table: a | row followed by a separator row
        if (line.startswith("|") and i + 1 < len(lines)
                and re.match(r"^\s*\|[\s:|-]+\|?\s*$", lines[i + 1])):
            close_lists()
            headers = [c.strip() for c in line.strip("|").split("|")]
            out.append('<table><thead><tr>'
                       + "".join(f"<th>{_inline(h)}</th>" for h in headers)
                       + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        if not line.strip():
            close_lists()
        elif re.match(r"^#{1,4}\s", line):
            close_lists()
            level = min(len(line) - len(line.lstrip("#")) + 2, 5)
            out.append(f"<h{level}>{_inline(line.lstrip('# ').strip())}</h{level}>")
        elif BULLET_RE.match(line):
            if not in_ul:
                close_lists()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(BULLET_RE.sub('', line))}</li>")
        elif NUMBERED_RE.match(line):
            if not in_ol:
                close_lists()
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{_inline(NUMBERED_RE.sub('', line))}</li>")
        elif line.startswith(">"):
            close_lists()
            out.append(f"<blockquote>{_inline(line.lstrip('> '))}</blockquote>")
        else:
            close_lists()
            out.append(f"<p>{_inline(line)}</p>")
        i += 1
    close_lists()
    return "\n".join(out)


def sections_to_html(md):
    """Split model output on '## ' headers into styled callout sections."""
    parts = re.split(r"(?m)^##\s+", md)
    html_out = [md_to_html(parts[0])] if parts[0].strip() else []
    for part in parts[1:]:
        header, _, body = part.partition("\n")
        emoji = next((e for e in SECTION_CLASS if e in header), None)
        cls = SECTION_CLASS.get(emoji, "plain")
        html_out.append(f'<section class="sec sec-{cls}">'
                        f"<h3>{_inline(header.strip())}</h3>"
                        f"{md_to_html(body)}</section>")
    return "\n".join(html_out)


CSS = """
@page { margin: 22mm 18mm; }
body { font-family: -apple-system, "Helvetica Neue", Georgia, serif;
       color: #1a1a1a; line-height: 1.55; max-width: 52em; margin: 0 auto;
       padding: 2em; }
h1 { font-size: 1.9em; border-bottom: 3px solid #1a355e; padding-bottom: .3em; }
h2.chapter { font-size: 1.45em; color: #1a355e; border-bottom: 2px solid #c8d3e8;
             padding: .9em 0 .25em; page-break-before: always; margin-top: 1.6em; }
h2.chapter:first-of-type { page-break-before: avoid; }
h3 { margin: 0 0 .5em; font-size: 1.05em; }
.meta { color: #666; font-style: italic; }
.pagespan { color: #666; font-size: .85em; font-weight: normal; }
.pg { color: #1a679e; font-size: .88em; white-space: nowrap; }
.sec { margin: 1em 0; padding: .8em 1em; border-radius: 8px;
       page-break-inside: avoid; background: #f7f8fa; border-left: 5px solid #b7c1d1; }
.sec-core     { background: #eef4ff; border-left-color: #2b5cad; }
.sec-actions  { background: #edf8ef; border-left-color: #2e8b57; }
.sec-quotes   { background: #fdf6e9; border-left-color: #c9962e; }
.sec-terms    { background: #f3eefa; border-left-color: #7a4fb0; }
.sec-stories  { background: #fff2f0; border-left-color: #c05b4d; }
.sec-mindset  { background: #eefafa; border-left-color: #2e8b8b; }
.sec-frameworks { background: #f4f4f4; border-left-color: #555; }
table { border-collapse: collapse; width: 100%; margin: .7em 0;
        font-size: .93em; background: #fff; }
th { background: #1a355e; color: #fff; text-align: left; padding: .45em .6em; }
td { border: 1px solid #ccd4e0; padding: .4em .6em; vertical-align: top; }
tr:nth-child(even) td { background: #f2f5f9; }
blockquote { margin: .6em 0; padding: .4em .9em; border-left: 4px solid #c9962e;
             background: #fdf6e9; font-style: italic; }
ul, ol { margin: .4em 0 .6em 1.4em; padding: 0; }
li { margin: .22em 0; }
.audit { background: #fff8f0; border: 1px solid #e0c9a6; padding: 1em;
         border-radius: 8px; }
.toc { columns: 2; font-size: .95em; }
"""


def build_html(book, meta_line, overview, chapters, glossary, audit_html, toc_items):
    toc = "".join(f'<li><a href="#ch{n}">{html_lib.escape(t)}</a></li>'
                  for n, t in toc_items)
    chapter_html = "".join(
        f'<h2 class="chapter" id="ch{n}">{n}. {html_lib.escape(title)} '
        f'<span class="pagespan">({pagespan})</span></h2>\n{sections_to_html(body)}'
        for n, title, pagespan, body in chapters)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{html_lib.escape(book)} — Expert Breakdown</title>
<style>{CSS}</style></head><body>
<h1>{html_lib.escape(book)}</h1>
<p class="meta">Chapter-by-chapter expert breakdown · {meta_line}</p>
{sections_to_html(overview)}
<h2 class="chapter">Contents</h2><ol class="toc">{toc}</ol>
{chapter_html}
<h2 class="chapter">📚 Master Glossary</h2>
{md_to_html(glossary)}
<h2 class="chapter">Appendix: Quote Audit</h2>
<div class="audit">{audit_html}</div>
</body></html>"""


def html_to_pdf(html_path):
    """Best-effort local HTML→PDF; returns pdf path or None."""
    pdf_path = html_path[:-5] + ".pdf"
    for chrome in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                   "/Applications/Chromium.app/Contents/MacOS/Chromium",
                   "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                   shutil.which("chromium") or "", shutil.which("google-chrome") or ""):
        if chrome and os.path.exists(chrome):
            r = subprocess.run([chrome, "--headless", "--disable-gpu",
                                f"--print-to-pdf={pdf_path}", "file://" + html_path],
                               capture_output=True, timeout=180)
            if r.returncode == 0 and os.path.exists(pdf_path):
                return pdf_path
    if shutil.which("wkhtmltopdf"):
        r = subprocess.run(["wkhtmltopdf", html_path, pdf_path], capture_output=True)
        if r.returncode == 0 and os.path.exists(pdf_path):
            return pdf_path
    if shutil.which("cupsfilter"):
        with open(pdf_path, "wb") as f:
            r = subprocess.run(["cupsfilter", html_path], stdout=f,
                               stderr=subprocess.DEVNULL)
        if r.returncode == 0 and os.path.getsize(pdf_path) > 2000:
            return pdf_path
        try:
            os.remove(pdf_path)
        except OSError:
            pass
    return None


# --------------------------------------------------------------------- main


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    model = DEFAULT_MODEL
    if "--model" in sys.argv:
        model = sys.argv[sys.argv.index("--model") + 1]

    path = args[0]
    if not os.path.isfile(path):
        for base in (WORK_DIR, os.path.expanduser("~/Documents/JarvisLibrary")):
            alt = os.path.join(base, path)
            if os.path.isfile(alt):
                path = alt
                break
        else:
            sys.exit(f"File not found: {args[0]}")

    security_check()
    if not check_ollama(model):
        sys.exit(1)

    book = os.path.splitext(os.path.basename(path))[0]
    print(f"📕 Reading: {book}")
    pages, exact = load_pages(path)
    # PDF pages are separate blocks; approx pages are slices of one continuous
    # text and must be rejoined seamlessly or verbatim quote checks break
    full_text = ("\n" if exact else "").join(pages)
    print(f"   {len(pages)} {'pages' if exact else 'approximate pages (~300 words each)'}")

    sections, structured = find_chapters(pages, exact)
    print(f"   {len(sections)} sections "
          + ("(chapter headings detected)" if structured else "(no headings found; even slices)"))

    opening = mark_pages(pages, 0, min(len(pages), 12), exact)
    overview = ask(model, OVERVIEW_PROMPT.format(text=opening[:CHUNK_CHARS]),
                   "overview & preface")

    chapters, terms_sections = [], []
    for n, (title, start, end) in enumerate(sections, 1):
        body = breakdown_section(model, f"'{title}'", mark_pages(pages, start, end, exact))
        pagespan = (f"pp. {start + 1}–{end}" if exact
                    else f"approx. pp. {start + 1}–{end}")
        chapters.append((n, title, pagespan, body))
        terms = re.search(r"##\s*📌[^\n]*\n(.*?)(?=\n##\s|\Z)", body, re.S)
        if terms:
            terms_sections.append(f"[{title}, {pagespan}]\n{terms.group(1).strip()}")

    glossary = ask(model, GLOSSARY_PROMPT.format(text="\n\n".join(terms_sections)[-40000:]),
                   "master glossary")

    all_md = overview + "\n" + "\n".join(b for _, _, _, b in chapters) + "\n" + glossary
    verified, fabricated = audit_quotes(all_md, full_text)
    audit_lines = [f"<p>✓ <strong>{verified}</strong> quote(s) verified verbatim "
                   "against the book text.</p>"]
    for q in fabricated:
        audit_lines.append("<p>⚠️ <strong>NOT FOUND in the book — do not use:</strong> "
                           f"“{html_lib.escape(q[:160])}”</p>")
    if not exact:
        audit_lines.append("<p>Note: this file format has no real page numbers; "
                           "citations are approximate pages of ~300 words.</p>")

    meta_line = (f"Generated {datetime.now():%B %d, %Y} · {len(pages)} pages · "
                 f"model {model} · quotes machine-verified against the text")
    page_html = build_html(book, meta_line, overview, chapters, glossary,
                           "\n".join(audit_lines),
                           [(n, t) for n, t, _, _ in chapters])

    os.makedirs(WORK_DIR, exist_ok=True)
    stem = os.path.join(WORK_DIR, "bookreport-" + re.sub(r"[^A-Za-z0-9-]+", "-", book))
    html_path = stem + ".html"
    with open(html_path, "w") as f:
        f.write(page_html)
    pdf_path = html_to_pdf(html_path)

    library = load_library()
    library[f"bookreport: {book}"] = {
        "notes": all_md[:100000],
        "text": full_text[:100000],
        "studied": datetime.now().isoformat(timespec="minutes"),
    }
    _write_private(LIBRARY_FILE, library)
    tool_remember_fact(f"I produced a full chapter-by-chapter expert breakdown of the book "
                       f"'{book}' and can discuss or quiz the user on it (it is in my library).")

    print(f"\n✅ Report: {pdf_path or html_path}")
    if not pdf_path:
        print(f"   (no PDF converter found — open {html_path} in your browser "
              "and press Cmd+P → Save as PDF; the layout is print-ready)")
    print(f"   Quote audit: {verified} verified, {len(fabricated)} flagged")
    if fabricated:
        print("   ⚠️ Flagged quotes are listed in the report appendix — treat them as unreliable.")
    print(f'   Jarvis can now discuss this book in chat — try: "quiz me on {book}"')


if __name__ == "__main__":
    main()
