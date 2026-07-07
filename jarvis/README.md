# J.A.R.V.I.S. — Your Free, Local AI Assistant 🤖

A personal AI assistant in the style of Tony Stark's J.A.R.V.I.S., running
**100% locally on your MacBook Pro**. No API keys, no subscription, no cloud —
the AI model lives on your machine and works even with Wi-Fi off.

## An honest note about "local Opus 4.8"

It is not possible for anyone to make a local copy of Claude Opus 4.8 (or any
Claude model). Those models are proprietary — the weights are never published,
so there is no code that can reproduce them, and anything claiming to be a
"local Opus" would be fake. What *is* possible — and what this project does —
is run excellent **open-weight models** (Llama 3.1, Qwen 2.5, etc.) locally
for free via [Ollama](https://ollama.com). On an Apple Silicon MacBook Pro
they're fast, private, and cost nothing to run. For actual Claude-level
answers you'd use the Claude API/app; for a free local Jarvis, this is the
real deal.

## Quick start

```bash
cd jarvis
./install.sh        # installs Ollama + downloads the model (one time, ~5GB)
python3 jarvis.py   # wake up Jarvis
```

That's it — no `pip install` needed, it's pure Python standard library.

## What Jarvis can do

- 💬 **Chat** with a proper J.A.R.V.I.S. personality (calls you "sir", dry wit)
- 🪪 **Rename him at will** — `/name Friday` (or anything) permanently renames
  your assistant; the personality, prompt labels, and spoken sign-off all follow
- 🔊 **Speak replies out loud** in any macOS voice — `/voice list` shows every
  voice installed on your Mac (male, female, other languages), `/voice Samantha`
  switches instantly and persists, `/voice off` mutes
- 🧠 **Learn permanently** — tell Jarvis your name, preferences, projects, or
  corrections and he stores them in a knowledge base that's injected into every
  future session, so he genuinely gets smarter about *you* over time
  (`/knowledge` to see what he knows, `/learn <fact>` to teach directly)
- 📝 **Produce real work** — ask for an essay, letter, plan, or code and he
  writes it and saves the file to `~/Documents/JarvisWork/`, then can read it
  back later to revise it
- 💾 **Remember conversations** between sessions (`/reset` to wipe)
- 🛠 **Actually do things** via tools:
  - open apps: *"Jarvis, open Safari"*
  - open websites: *"pull up youtube.com"*
  - system vitals: *"how's my Mac doing?"* (battery, disk, memory, uptime)
  - timers: *"set a timer for 10 minutes for the pasta"* — announced out loud
  - time & date: *"what time is it?"*
- ⚡ **One-shot mode**: `python3 jarvis.py "remind me what day it is"`

## Legal work mode ⚖️

Turn it on with `/legal on`. Jarvis switches to strict paperwork discipline for
reading briefs, summarizing case files, and drafting documents (summonses,
complaints, letters, memoranda):

1. **Load the case materials** — drop them in `~/Documents/JarvisWork/`
   (`.pdf`, `.docx`, `.rtf`, `.txt`, `.md` all work) and say
   *"read complaint.pdf"*.
2. **Draft with `/draft`** — e.g. `/draft a summons for the defendant in the
   loaded complaint`. Jarvis produces it in three passes: full draft →
   ruthless self-critique (as a senior partner reviewing a junior's work) →
   final revision. This self-review loop is how he catches his own mistakes.
3. **Automatic citation audit** — every citation in the output is checked
   *verbatim* against the documents he's actually read. Verified ones are
   marked ✓; anything he can't trace to a source is flagged
   **NOT FOUND — verify before use** right in the saved file. He is under
   standing orders to never cite from memory and to write
   `[CITATION NEEDED — verify]` rather than guess.

### The honest truth about "attorney-level, zero errors"

No AI — local, cloud, free, or $1,000/month — can guarantee error-free legal
work or perfect citations. Frontier models still fabricate case law
occasionally, and real attorneys have been sanctioned by real judges for
filing AI-invented citations. That is exactly why Jarvis's legal mode is built
around **verification, not trust**: forbidden from citing anything outside his
sources, plus an automatic audit that flags what it can't verify. Treat him as
a tireless junior associate who does the reading and drafting; a qualified
human must review anything before it's signed, filed, or served — and only a
licensed attorney can practice law. Every draft he saves carries that
disclaimer.

## Limited web research 🔎

Off by default. `/web on` grants Jarvis research access **restricted to
`.edu`, `.gov`, and `.org` sites only** — he cannot pull information from
anywhere else, and the restriction is enforced by code on every search and
every page fetch (including the librarian's automatic study runs):

- Search backends: **Semantic Scholar** (academic papers, all fields),
  **arXiv** (preprints), **Open Library** (books), and **CourtListener**
  (case law) — plus fetching from any university (`.edu`), government
  (`.gov`), or nonprofit (`.org`) site
- **Verified legal sources** are allowed by default: courtlistener.com and
  justia.com (real case law, codes, and regulations), alongside `.gov` court
  sites and `.edu` law-school sources like law.cornell.edu
- **Wikipedia is blocked** — it's a `.org`, but per your standards it's on
  the untrusted blocklist. Add more distrusted sites one per line in
  `~/.jarvis_blocked.txt`; the blocklist wins over the allowlist
- Need a specific exception? Add trusted domains one per line in
  `~/.jarvis_domains.txt`
- Every page he fetches is registered as a **loaded source**, so the citation
  audit can verify his citations against what he actually read
- He's instructed to tell you which sources he used, with URLs
- `/web off` returns him to fully offline; he starts offline every session

Ask things like: *"search for papers on transformer interpretability, read the
two best ones, and summarize them with links."*

## Academic mode — MSW student profile 🎓✏️

`/school on` activates a **persistent** academic profile (it survives
restarts, unlike the other modes). Jarvis then applies two rulebooks to all
schoolwork, automatically:

**Your school's AI-usage policy** (per NASW Code of Ethics 4.04):
- AI supports your learning; it never replaces your original thinking —
  Jarvis positions himself as feedback, research, and editing help
- All AI use on submitted work must be disclosed and cited
- Grammar/clarity editing follows the two-version rule via **`/edit
  my-paper.md`**: your original draft is never touched, the AI-assisted
  version is saved separately with the required footnote naming the AI tool,
  and Jarvis reminds you to submit **both**
- He knows Turnitin AI detection runs in Canvas (AI score starts at 25%,
  separate from the similarity score) and will remind you of disclosure
  duties whenever you ask for writing help

**APA Publication Manual, 7th Edition** — every paper:
- Student title page (title, name, institution, course number and name,
  instructor, due date, page count) with **no running head**
- All five heading levels formatted correctly
- Singular "they" as gender-neutral; one space after periods
- In-text: 3+ authors cited as First Author et al. from the first citation
- References: up to 20 authors then ellipsis; DOIs/URLs as hyperlinks; no
  "DOI:" label; "Retrieved from" only with a retrieval date

The profile is school-agnostic — it follows you to any program:

```
/school show                      # see the profile
/school name Rodney               # the name on every paper (default)
/school school Tulane University  # swap when you change schools
/school course SOWK 6000: Foundations
/school instructor Dr. Smith
```

## Academic work 🎓

Jarvis is built to be your research assistant, not your ghostwriter. For a
graduate paper he can: find and summarize sources (`/web on`), build an
annotated outline from your instructions, critique your drafts hard
(*"review my draft like a harsh professor"*), and check your citations.
`/draft` can produce full-length prose, but know the stakes: submitting
AI-written work as your own is academic misconduct at most universities and
a serious risk in graduate school. Check your program's AI policy — many
allow disclosed AI assistance for research and editing. The work he saves to
`~/Documents/JarvisWork/` is most valuable as raw material you rewrite in
your own voice. For long documents, work section by section and use the
biggest model your Mac can run.

## How to train Jarvis 🎯

You don't retrain the neural network — you shape his behavior, and it sticks.
Four levers, in order of impact:

**1. Give him standing orders with `/learn`.** Anything you teach becomes a
permanent instruction injected into every future session:

```
/learn Always cite sources in APA format
/learn When I ask for research, give me a bullet list of findings with a URL for each
/learn My papers are for a public-administration graduate program; write at that level
/learn Never use bullet points in final drafts — full paragraphs only
```

**2. Correct him in conversation.** When he does something wrong, say so —
*"No — next time show the source URL before the summary"* — he's instructed
to store corrections permanently via his `remember_fact` tool. Check what
stuck with `/knowledge`; remove bad habits with `/forget` (then re-teach).

**3. Be specific in the request.** Local models reward precision. Include:
what to produce, for whom, how long, in what format, from which sources.
Weak: *"research housing policy"*. Strong: *"search .gov and .edu sources on
Section 8 housing policy since 2020, read the three best, and give me a
one-page summary with a citation and URL for each claim."*

**4. Feed his library.** Drop model examples — papers you got A's on, briefs
written the way you like — into `~/Documents/JarvisLibrary/`. He studies
them overnight and can imitate: *"search your library for my writing style
and match it."*

## Book breakdowns — become fluent in a book without reading it all 📕

```bash
python3 bookreport.py mybook.pdf                    # PDFs give exact page numbers
python3 bookreport.py mybook.pdf --model qwen2.5:32b   # bigger model = better report
```

Jarvis reads the entire book and produces a professionally formatted report
(HTML, auto-converted to PDF when Chrome/Edge is installed — otherwise open
the HTML and press Cmd+P → Save as PDF; the layout is print-ready). Written
for a reader who has never heard of the book:

- **Opening**: 🏛 what the book is about + 📝 the preface/front matter
- **Every chapter**, with these sections: 📜 Overview · 💬 Key Quotes
  (verbatim, page-cited) · 📖 Stories & Case Examples (the author's real
  ones) · 🎯 Core Teachings · 📊 Frameworks & Tables (reproduced from the
  book) · 📌 Key Terms (a chapter glossary) · ✅ Actionable Lessons ·
  🧠 Mindset & Philosophical Insights · 🔮 Metaphors & Analogies ·
  🤔 Questions for Reflection
- **Master glossary** at the end: every term, alphabetized, with definitions
  and page references
- **Page references throughout** so you can go back to the source (exact for
  PDFs; approximate and labeled as such for .txt/.docx)
- **Colored callout boxes** and styled tables; chapters start on new pages
  in the PDF
- Supplementary real-world examples are allowed but always labeled
  *"Supplementary example (not from the book)"* — they never replace the
  author's own material
- **Automatic quote audit**: every quote is machine-checked verbatim against
  the book; anything untraceable is flagged in the appendix
- The finished report joins Jarvis's library, so you can say *"quiz me on
  chapter 3"* in chat afterwards

*Honest limit:* a great breakdown makes you conversant and test-ready —
key arguments, case studies, terms, page refs — but summaries compress; for
close-reading exams or literature seminars, spot-check the flagged pages in
the original. Use books you own; the report is your personal study aid.

## Autonomous study — Jarvis learns without being asked 📚

`librarian.py` is Jarvis's self-study system. Once scheduled, he reads and
learns every night on his own:

```bash
python3 librarian.py --schedule   # install the nightly 2 AM study session
```

- **Reads whatever you drop in `~/Documents/JarvisLibrary/`** — books, legal
  briefs, case files (`.pdf`, `.docx`, `.txt`, …). Each new file gets studied:
  he writes structured notes (summary, key points, citations found, lessons)
  into his permanent library and remembers that he studied it.
- **Fetches real case law from the web** — list topics in
  `~/Documents/JarvisLibrary/topics.txt` (e.g. `breach of contract`) and each
  nightly run downloads matching real court opinions from
  [CourtListener](https://www.courtlistener.com) (the Free Law Project's
  public-domain database — a trustworthy source, not random web scraping).
  Skip `--web` for zero internet use.
- **Everything he studies compounds**: his library is searchable in
  conversation, listed in his mind at startup, and counts as verification
  sources for the citation audit.

Check on him anytime: `python3 librarian.py --status`.

*Honest limit:* "learning" means growing his knowledge library and study
notes — the most a laptop can do. The neural network itself doesn't retrain;
to raise his raw reasoning power, switch to a bigger model (`/model
qwen2.5:32b`) — his entire library and knowledge carry over.

## How "learning" works (and its honest limits)

Jarvis learns the way that's actually possible on a laptop: a **persistent
knowledge base**. Facts you teach him (or that he decides to keep) go into
`~/.jarvis_knowledge.json` and are loaded into his mind at every startup. He
does not retrain the neural network itself — nobody's laptop can do that, and
any tool claiming otherwise is overselling. To upgrade his raw intelligence,
pull a bigger model (see table below); his learned knowledge carries over
automatically since it lives outside the model.

## Research accuracy

Jarvis is instructed to never invent facts, statistics, or citations, and to
say plainly when he isn't sure. Keep two things in mind:

- He runs **fully offline** — that's the privacy/security win you asked for,
  but it means no live web lookups. His general knowledge stops at his model's
  training date.
- Local 7–8B models are good but not infallible. For anything high-stakes,
  ask him to flag uncertainty (*"mark anything you're not sure of"*) and
  verify the flagged parts yourself.

## Security: local-only by design

- **Everything stays on your Mac.** The model runs in Ollama on `localhost`;
  no chat, memory, or documents ever leave your machine.
- **Refuses remote servers.** If `JARVIS_OLLAMA_URL` is ever pointed at a
  non-localhost address, Jarvis refuses to start rather than send your data out.
- **Web access is opt-in and fenced.** Research mode starts disabled every
  session, and even when enabled Jarvis can only reach `.edu`, `.gov`, and
  `.org` sites (plus your explicit additions) — any other domain is refused
  in code, on searches and fetches alike.
- **Private files.** Memory and knowledge files are written with `chmod 600`
  (readable by your user account only).
- **No arbitrary command execution.** Jarvis's tools are a fixed allowlist
  (open app, open URL, timers, system stats, documents) — the model cannot run
  shell commands, and document access is confined to `~/Documents/JarvisWork/`
  with path-traversal blocked.
- **Nothing listens for connections.** Jarvis makes no inbound network
  surface; Ollama itself binds to localhost by default. Standard Mac hygiene
  (FileVault on, firewall on, OS updates) covers the rest — there's no cloud
  account here to be hacked.

## Commands

| Command | Effect |
|---|---|
| `/name <name>` | rename your assistant, permanently (until you rename again) |
| `/voice on\|off\|list\|<voice>` | toggle speech, list macOS voices, or pick one |
| `/model <name>` | switch models, e.g. `/model qwen2.5:7b` |
| `/legal on\|off` | legal work mode: strict citation & drafting rules |
| `/school ...` | academic mode (persistent): APA 7 + AI-policy rules |
| `/edit <file>` | two-version AI editing with disclosure footnote |
| `/web on\|off` | research access, allowlisted scholarly sites only |
| `/draft <desc>` | draft → self-critique → revise → citation audit → save |
| `/learn <fact>` | teach Jarvis something permanently |
| `/knowledge` | show everything Jarvis has learned |
| `/forget` | wipe the learned knowledge base |
| `/reset` | clear conversation memory |
| `/help` | show commands |
| `/quit` | exit |

## Choosing a model

The default is `llama3.1:8b` (good all-rounder with tool support, ~5GB).
Depending on your MacBook Pro's RAM:

| RAM | Recommended | Pull with |
|---|---|---|
| 8 GB | `llama3.2:3b` | `ollama pull llama3.2:3b` |
| 16 GB | `llama3.1:8b` (default) or `qwen2.5:7b` | `ollama pull qwen2.5:7b` |
| 32 GB+ | `qwen2.5:32b` | `ollama pull qwen2.5:32b` |

Switch anytime with `/model <name>` or set `JARVIS_MODEL=qwen2.5:7b` in your shell.

## How it works

```
You ──▶ jarvis.py ──▶ Ollama (local server on your Mac) ──▶ open-weight LLM
              │
              ├─ tools: open apps/sites, timers, system stats, documents,
              │         library search
              ├─ voice: macOS `say`
              ├─ memory: ~/.jarvis_memory.json         (conversation)
              ├─ knowledge: ~/.jarvis_knowledge.json   (learned facts)
              ├─ library: ~/.jarvis_library.json       (study notes + texts)
              ├─ reading pile: ~/Documents/JarvisLibrary/  (drop files here)
              └─ work: ~/Documents/JarvisWork/         (documents he writes)

librarian.py (nightly, via launchd) ──▶ studies new files, optionally fetches
                                        court opinions from CourtListener
```

Everything stays on your machine. Network is used only for the one-time model
download, websites you ask Jarvis to open, and — only if you enable `--web`
study — fetching public court opinions from CourtListener.
