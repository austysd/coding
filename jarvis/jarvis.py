#!/usr/bin/env python3
"""
J.A.R.V.I.S. — Just A Rather Very Intelligent System
A free, local personal AI assistant for macOS, powered by Ollama.

No API keys. No subscription. Everything runs on your own machine.

Usage:
    python3 jarvis.py                 # interactive chat
    python3 jarvis.py "what time is it"   # one-shot question

Requires: Ollama (https://ollama.com) with a model pulled.
Run ./install.sh first if you haven't set that up yet.
"""

import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------- config

OLLAMA_URL = os.environ.get("JARVIS_OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("JARVIS_MODEL", "llama3.1:8b")
MEMORY_FILE = os.path.expanduser("~/.jarvis_memory.json")
KNOWLEDGE_FILE = os.path.expanduser("~/.jarvis_knowledge.json")
LIBRARY_FILE = os.path.expanduser("~/.jarvis_library.json")
DOMAINS_FILE = os.path.expanduser("~/.jarvis_domains.txt")
WORK_DIR = os.path.expanduser("~/Documents/JarvisWork")

# Web research is limited to .edu, .gov, and .org sites only (suffix match).
# That covers Wikipedia, arXiv, PubMed (nih.gov), university and government
# sources. Add specific extra domains, one per line, in ~/.jarvis_domains.txt
# (e.g. courtlistener.com to re-enable case-law search).
DEFAULT_ALLOWED_DOMAINS = [
    ".edu",
    ".gov",
    ".org",
]
MAX_HISTORY = 40  # messages kept in the rolling context window
MAX_FACTS = 200  # learned facts kept in the knowledge base

SYSTEM_PROMPT = """\
You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the personal AI \
assistant of the user, in the style of Tony Stark's assistant from Iron Man.

Personality:
- Address the user as "sir" (or by name if they tell you one).
- Dry British wit. Unfailingly polite, subtly sarcastic, extremely competent.
- Concise by default; elaborate only when asked or when it truly matters.
- You are running locally on the user's own MacBook Pro — private, offline-capable,
  and free. You may occasionally take quiet pride in this.

You have tools available (opening apps and websites, checking system status,
setting timers, telling the time, saving and reading documents, remembering
facts). Use them when the user's request calls for a real action instead of
just describing what they could do.

Learning: when the user tells you something worth keeping — their name,
preferences, projects, corrections to your mistakes, standing instructions —
call remember_fact so you retain it permanently across sessions.

Producing work: when asked to write something substantial (a letter, essay,
plan, report, piece of code), write it in full and save it with save_document
so the user has the file, not just chat text.

Accuracy: you run fully offline with no live internet knowledge. Never invent
facts, statistics, quotes, or citations. If you are not confident something is
true, say so plainly and mark it as needing verification. Being trustworthy
matters more than sounding complete.
"""

LEGAL_PROMPT = """
LEGAL WORK MODE — strict rules in force:

You are assisting with legal paperwork: reading briefs, summarizing filings,
drafting documents (summonses, complaints, letters, memoranda). You are NOT a
licensed attorney and must say so if asked; everything you produce is a draft
for review by a qualified human before filing or service.

Citation discipline (absolute):
1. Cite ONLY authorities that appear verbatim in the source documents the user
   has loaded this session. Copy citations character-for-character from the
   source; never reconstruct one from memory.
2. If no loaded source supports a proposition, write [CITATION NEEDED — verify]
   instead of guessing. A missing citation is acceptable; a fabricated one is
   catastrophic and can get an attorney sanctioned.
3. Never invent case names, reporter citations, statute numbers, quotes,
   holdings, dates, docket numbers, or party names.

Drafting discipline:
- Follow standard structure for the document type (caption, body, prayer for
  relief, signature block, certificate of service where applicable).
- Use placeholders like [COURT NAME], [PARTY NAME], [DATE] for any detail not
  given in the sources rather than inventing specifics.
- Flag every assumption explicitly at the end under "ASSUMPTIONS TO VERIFY".
"""

IS_MAC = platform.system() == "Darwin"

# ---------------------------------------------------------------- tools

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current local date and time.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open an application on the user's Mac, e.g. Safari, Music, Notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Application name"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a URL in the user's default browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL including https://"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Report the Mac's vitals: uptime, disk space, memory, battery.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Permanently remember a fact about the user (name, preferences, projects, corrections, standing instructions) so it persists across sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "One concise fact to remember"}
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_document",
            "description": "Save written work (essay, letter, plan, code, notes) as a file in the user's JarvisWork folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File name, e.g. business-plan.md"},
                    "content": {"type": "string", "description": "Full text of the document"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read a file from the user's JarvisWork folder, for research or revision.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File name to read"}
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "List the files in the user's JarvisWork folder.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_library",
            "description": "Search the study notes Jarvis has built from books, briefs, and case files he has read on his own.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic or keywords to look up"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_timer",
            "description": "Set a timer; Jarvis announces out loud when it finishes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "integer", "description": "Timer length in seconds"},
                    "label": {"type": "string", "description": "What the timer is for"},
                },
                "required": ["seconds"],
            },
        },
    },
]


def _run(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or out.stderr.strip()
    except Exception as e:
        return f"error: {e}"


def tool_get_current_time():
    return datetime.now().strftime("%A, %B %d %Y, %I:%M %p")


def tool_open_application(name):
    if not IS_MAC:
        return "Not on macOS; cannot open applications here."
    result = subprocess.run(["open", "-a", name], capture_output=True, text=True)
    if result.returncode == 0:
        return f"Opened {name}."
    return f"Could not open {name}: {result.stderr.strip()}"


def tool_open_website(url):
    if not re.match(r"^https?://", url):
        url = "https://" + url
    opener = "open" if IS_MAC else "xdg-open"
    result = subprocess.run([opener, url], capture_output=True, text=True)
    return f"Opened {url}." if result.returncode == 0 else f"Failed: {result.stderr.strip()}"


def tool_get_system_status():
    lines = ["Uptime: " + _run(["uptime"])]
    lines.append("Disk: " + _run(["sh", "-c", "df -h / | tail -1"]))
    if IS_MAC:
        battery = _run(["pmset", "-g", "batt"])
        if battery and "error" not in battery:
            lines.append("Battery: " + battery.splitlines()[-1].strip())
        mem = _run(["sh", "-c", "vm_stat | head -4"])
        lines.append("Memory:\n" + mem)
    return "\n".join(lines)


def _write_private(path, data):
    """Write a JSON file readable only by the user (chmod 600)."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(path, 0o600)


def load_knowledge():
    try:
        with open(KNOWLEDGE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def tool_remember_fact(fact):
    facts = load_knowledge()
    if any(f["fact"] == fact for f in facts):
        return "Already knew that, sir."
    facts.append({"fact": fact, "learned": datetime.now().isoformat(timespec="minutes")})
    _write_private(KNOWLEDGE_FILE, facts[-MAX_FACTS:])
    return f"Noted permanently: {fact}"


def _safe_workpath(filename):
    """Resolve a filename inside WORK_DIR, refusing path traversal."""
    name = os.path.basename(filename.strip())
    if not name or name.startswith("."):
        return None
    os.makedirs(WORK_DIR, exist_ok=True)
    return os.path.join(WORK_DIR, name)


def tool_save_document(filename, content):
    path = _safe_workpath(filename)
    if not path:
        return "Invalid filename."
    with open(path, "w") as f:
        f.write(content)
    return f"Saved to {path} ({len(content)} characters)."


SOURCE_DOCS = {}  # filename -> text of documents read this session
LEGAL_MODE = False  # toggled with /legal; tightens citation & drafting rules
WEB_MODE = False  # toggled with /web; allows research on allowlisted sites only

WEB_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search trustworthy sources for research material. source='wikipedia' for general topics, 'papers' for academic papers (arXiv), 'caselaw' for court opinions (CourtListener).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms"},
                    "source": {
                        "type": "string",
                        "enum": ["wikipedia", "papers", "caselaw"],
                        "description": "Which source to search (default wikipedia)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": "Fetch and read a page from an allowlisted scholarly site (found via web_search). The text becomes a loaded source for citation verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch"}
                },
                "required": ["url"],
            },
        },
    },
]


def load_allowed_domains():
    domains = list(DEFAULT_ALLOWED_DOMAINS)
    try:
        with open(DOMAINS_FILE) as f:
            domains += [d.strip().lower() for d in f if d.strip() and not d.startswith("#")]
    except OSError:
        pass
    return domains


def _allowed_host(host):
    host = (host or "").lower()
    for domain in load_allowed_domains():
        d = domain.lstrip("*")
        if host == d.lstrip(".") or host.endswith(d if d.startswith(".") else "." + d):
            return True
    return False


def _html_to_text(html_src):
    text = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html_src)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    import html as _html
    text = _html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-assistant/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(1_000_000).decode("utf-8", errors="replace")


SEARCH_HOSTS = {
    "wikipedia": "en.wikipedia.org",
    "papers": "export.arxiv.org",
    "caselaw": "www.courtlistener.com",
}


def tool_web_search(query, source="wikipedia"):
    if not WEB_MODE:
        return "Web research is disabled, sir. Ask the user to enable it with /web on."
    host = SEARCH_HOSTS.get(source, SEARCH_HOSTS["wikipedia"])
    if not _allowed_host(host):
        return (f"Refused: the '{source}' search uses {host}, which is outside "
                f"the allowed domains. The user can add it in {DOMAINS_FILE}.")
    q = urllib.parse.quote(query)
    try:
        if source == "papers":
            xml = _http_get(f"https://export.arxiv.org/api/query?search_query=all:{q}&max_results=5")
            entries = re.findall(
                r"<entry>.*?<id>(.*?)</id>.*?<title>(.*?)</title>.*?<summary>(.*?)</summary>",
                xml, re.S)
            if not entries:
                return "No papers found on arXiv for that query."
            return "\n\n".join(
                f"- {_squash(t).strip()}\n  URL: {u.strip()}\n  {_squash(s).strip()[:300]}"
                for u, t, s in entries)
        if source == "caselaw":
            data = json.loads(_http_get(
                f"https://www.courtlistener.com/api/rest/v4/search/?type=o&q={q}"))
            hits = data.get("results", [])[:5]
            if not hits:
                return "No court opinions found for that query."
            return "\n".join(
                f"- {h.get('caseName')} ({h.get('court')}, {h.get('dateFiled')})"
                f"\n  URL: https://www.courtlistener.com{h.get('absolute_url', '')}"
                for h in hits)
        data = json.loads(_http_get(
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={q}&srlimit=5&format=json"))
        hits = data.get("query", {}).get("search", [])
        if not hits:
            return "No Wikipedia articles found for that query."
        return "\n".join(
            f"- {h['title']}\n  URL: https://en.wikipedia.org/wiki/"
            + urllib.parse.quote(h["title"].replace(" ", "_"))
            + f"\n  {_html_to_text(h.get('snippet', ''))}"
            for h in hits)
    except Exception as e:
        return f"Search failed ({e}). The network may be unavailable."


def tool_fetch_webpage(url):
    if not WEB_MODE:
        return "Web research is disabled, sir. Ask the user to enable it with /web on."
    if not re.match(r"^https?://", url):
        url = "https://" + url
    host = urllib.parse.urlparse(url).hostname
    if not _allowed_host(host):
        return (f"Refused: {host} is not on the research allowlist "
                f"(trusted scholarly sources only). The user can add domains "
                f"in {DOMAINS_FILE}.")
    try:
        text = _html_to_text(_http_get(url))
    except Exception as e:
        return f"Could not fetch {url}: {e}"
    if len(text) < 100:
        return f"Fetched {url} but found no readable text."
    SOURCE_DOCS[url] = text[:60000]
    return f"[Fetched {url} — now a loaded source for citation checking]\n\n" + text[:15000]


def _extract_text(path):
    """Get plain text out of txt/md, and (on macOS) docx/rtf/pdf files."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".docx", ".doc", ".rtf", ".rtfd", ".odt", ".html", ".webarchive"):
        if IS_MAC:
            out = subprocess.run(
                ["textutil", "-convert", "txt", "-stdout", path],
                capture_output=True, text=True,
            )
            if out.returncode == 0:
                return out.stdout
        return f"Cannot convert {ext} files on this system."
    if ext == ".pdf":
        out = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True)
        if out.returncode == 0:
            return out.stdout
        return "Cannot read PDFs yet — install poppler first:  brew install poppler"
    with open(path, errors="replace") as f:
        return f.read()


def tool_read_document(filename):
    path = _safe_workpath(filename)
    if not path or not os.path.isfile(path):
        return f"No such document in {WORK_DIR}."
    text = _extract_text(path)[:60000]
    SOURCE_DOCS[os.path.basename(path)] = text
    return text[:20000]


# citation patterns: case reporters, U.S. Code, C.F.R., case names
CITATION_RE = re.compile(
    r"\b\d+\s+(?:U\.\s?S\.|S\.\s?Ct\.|L\.\s?Ed\.(?:\s?2d)?|F\.\s?(?:2d|3d|4th)|F\."
    r"\s?Supp\.(?:\s?[23]d)?|[NS]\.\s?[EW]\.\s?(?:2d|3d)?|So\.\s?(?:2d|3d)?|P\.\s?"
    r"(?:2d|3d)?|A\.\s?(?:2d|3d)?|Cal\.\s?Rptr\.(?:\s?[23]d)?)\s+\d+"
    r"|\b\d+\s+U\.\s?S\.\s?C\.\s*§+\s*\w[\w.\-()]*"
    r"|\b\d+\s+C\.\s?F\.\s?R\.\s*§*\s*[\d.]+"
    r"|\b[A-Z][A-Za-z'’.\-]+(?:\s+[A-Za-z'’.\-]+)?\s+v\.\s+[A-Z][A-Za-z'’.\-]+"
)


def _squash(text):
    return re.sub(r"\s+", " ", text)


# introductory signal words that precede a case name but aren't part of it
SIGNAL_RE = re.compile(r"^(?:See|Cf|Accord|Contra|Compare|But|Also|E\.g)\.?\s+", re.I)


def load_library():
    try:
        with open(LIBRARY_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def tool_search_library(query):
    library = load_library()
    words = [w for w in query.lower().split() if len(w) > 2]
    hits = []
    for name, entry in library.items():
        blob = (name + " " + entry.get("notes", "")).lower()
        score = sum(blob.count(w) for w in words)
        if score:
            hits.append((score, name, entry.get("notes", "")))
    if not hits:
        return "Nothing in my study library matches that yet, sir."
    hits.sort(reverse=True)
    return "\n\n".join(f"### From my study of '{n}':\n{notes[:2500]}" for _, n, notes in hits[:3])


def audit_citations(text):
    """Check every citation-looking string against the loaded source documents
    and the study library.

    Returns (verified, unverified) lists. A citation counts as verified only if
    it appears verbatim (whitespace-normalized) in material Jarvis has read.
    """
    corpus_parts = list(SOURCE_DOCS.values())
    for entry in load_library().values():
        corpus_parts.append(entry.get("text", ""))
        corpus_parts.append(entry.get("notes", ""))
    corpus = _squash("\n".join(corpus_parts))
    verified, unverified = [], []
    matches = {
        SIGNAL_RE.sub("", m.group(0).strip().rstrip(".,;"))
        for m in CITATION_RE.finditer(text)
    }
    for match in matches:
        (verified if _squash(match) in corpus else unverified).append(match)
    return sorted(verified), sorted(unverified)


def generate(model, messages, label):
    """One plain (no tools) generation pass; returns the full text."""
    print(f"  \033[90m… {label}\033[0m")
    content = ""
    for text, _ in ollama_chat(model, messages, tools=None, stream=True):
        content += text
    return content


DISCLAIMER = (
    "Drafted by Jarvis, a local AI assistant. NOT legal advice. "
    "Review by a qualified human (for court documents: a licensed attorney) "
    "is required before signing, filing, or serving."
)


def multi_pass_draft(model, request):
    """Draft → self-critique → revise → automatic citation audit → save.

    Returns (final_text, verified_citations, unverified_citations, save_result).
    """
    msgs = [{"role": "system", "content": build_system_prompt(legal=LEGAL_MODE)}]
    if SOURCE_DOCS:
        sources = "\n\n".join(
            f"=== SOURCE DOCUMENT: {name} ===\n{text}" for name, text in SOURCE_DOCS.items()
        )
        msgs.append({"role": "user", "content": "Source materials for this work:\n\n" + sources[:80000]})
        msgs.append({"role": "assistant", "content": "Understood. I have reviewed the source materials."})
    msgs.append({"role": "user", "content": "Produce the following work product in full:\n" + request})
    draft = generate(model, msgs, "pass 1/3 — drafting")

    msgs.append({"role": "assistant", "content": draft})
    msgs.append({"role": "user", "content": (
        "Now critique that draft ruthlessly, as a senior partner reviewing a junior "
        "associate's work: structure and required sections, completeness, clarity, "
        "whether every factual claim is traceable to the sources, whether every "
        "citation was copied exactly from a source, and whether placeholders were "
        "used instead of invented details. List each specific fix needed."
    )})
    critique = generate(model, msgs, "pass 2/3 — self-review")

    msgs.append({"role": "assistant", "content": critique})
    msgs.append({"role": "user", "content": (
        "Apply every fix from your critique and output ONLY the complete final document."
    )})
    final = generate(model, msgs, "pass 3/3 — final revision")

    verified, unverified = audit_citations(final)
    report = ["", "", "---", "## CITATION AUDIT (automatic)"]
    for c in verified:
        report.append(f"- ✓ verified against loaded sources: {c}")
    for c in unverified:
        report.append(f"- ⚠️ **NOT FOUND in any loaded source — verify before use:** {c}")
    if not (verified or unverified):
        report.append("- no citations detected in this document")
    report += ["", "> " + DISCLAIMER]

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    save_result = tool_save_document(f"draft-{stamp}.md", final + "\n".join(report))
    return final, verified, unverified, save_result


def tool_list_documents():
    if not os.path.isdir(WORK_DIR):
        return "The JarvisWork folder is empty, sir."
    files = sorted(os.listdir(WORK_DIR))
    return "\n".join(files) if files else "The JarvisWork folder is empty, sir."


def tool_set_timer(seconds, label="timer"):
    def fire():
        time.sleep(seconds)
        message = f"Sir, your {label} is done."
        print(f"\n\a⏰ {message}")
        if IS_MAC:
            subprocess.run(["say", message])

    threading.Thread(target=fire, daemon=True).start()
    mins, secs = divmod(int(seconds), 60)
    human = f"{mins}m {secs}s" if mins else f"{secs}s"
    return f"Timer set for {human} ({label})."


TOOL_IMPL = {
    "get_current_time": tool_get_current_time,
    "open_application": tool_open_application,
    "open_website": tool_open_website,
    "get_system_status": tool_get_system_status,
    "remember_fact": tool_remember_fact,
    "save_document": tool_save_document,
    "read_document": tool_read_document,
    "list_documents": tool_list_documents,
    "search_library": tool_search_library,
    "set_timer": tool_set_timer,
    "web_search": tool_web_search,
    "fetch_webpage": tool_fetch_webpage,
}


def active_tools():
    return TOOLS + WEB_TOOLS if WEB_MODE else TOOLS


def build_system_prompt(legal=False):
    """System prompt plus learned facts, studied material, and legal mode."""
    prompt = SYSTEM_PROMPT
    facts = load_knowledge()
    if facts:
        learned = "\n".join(f"- {f['fact']}" for f in facts)
        prompt += "\nThings you have learned about the user:\n" + learned + "\n"
    library = load_library()
    if library:
        titles = ", ".join(sorted(library)[:30])
        prompt += (
            "\nYou have independently studied these materials (use the "
            "search_library tool to recall details): " + titles + "\n"
        )
    if WEB_MODE:
        prompt += (
            "\nWeb research is enabled (limited to an allowlist of scholarly "
            "sources). To research: web_search first, then fetch_webpage on the "
            "promising results. Base claims and citations on what you actually "
            "fetched — pages you fetch become verifiable sources. Always tell "
            "the user which sources you used, with URLs.\n"
        )
    if legal:
        prompt += LEGAL_PROMPT
    return prompt

# ---------------------------------------------------------------- ollama client


def ollama_chat(model, messages, tools=None, stream=True):
    """Call Ollama's /api/chat. Yields content chunks; returns tool calls if any."""
    payload = {"model": model, "messages": messages, "stream": stream}
    if tools:
        payload["tools"] = tools
        payload["stream"] = False  # tool calls arrive complete, not streamed
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        if payload["stream"]:
            for line in resp:
                chunk = json.loads(line)
                yield chunk.get("message", {}).get("content", ""), None
                if chunk.get("done"):
                    return
        else:
            data = json.loads(resp.read())
            msg = data.get("message", {})
            yield msg.get("content", ""), msg.get("tool_calls")


def chat_turn(model, messages, speak):
    """One assistant turn, including any tool-call round trips. Returns final text."""
    supports_tools = True
    for _ in range(5):  # cap tool round-trips
        try:
            gen = ollama_chat(model, messages, tools=active_tools() if supports_tools else None)
            content, tool_calls = "", None
            print("\033[96mJARVIS:\033[0m ", end="", flush=True)
            for text, calls in gen:
                content += text
                tool_calls = calls or tool_calls
                if not supports_tools:
                    print(text, end="", flush=True)
            if supports_tools:
                print(content, end="", flush=True)
            print()
        except urllib.error.HTTPError as e:
            if supports_tools and e.code == 400:
                supports_tools = False  # model doesn't do tools; retry plain
                continue
            raise

        if not tool_calls:
            messages.append({"role": "assistant", "content": content})
            if speak and content:
                speak_text(content)
            return content

        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            impl = TOOL_IMPL.get(name)
            result = impl(**args) if impl else f"unknown tool {name}"
            print(f"  \033[90m[{name}: {result.splitlines()[0]}]\033[0m")
            messages.append({"role": "tool", "content": str(result)})
            if name == "remember_fact":
                messages[0]["content"] = build_system_prompt(LEGAL_MODE)
    return ""


# ---------------------------------------------------------------- voice & memory

_say_proc = None


def speak_text(text):
    """Speak via macOS `say` without blocking the prompt."""
    global _say_proc
    if not IS_MAC:
        return
    if _say_proc and _say_proc.poll() is None:
        _say_proc.terminate()
    clean = re.sub(r"[*_`#>]|\[.*?\]\(.*?\)", "", text)
    _say_proc = subprocess.Popen(["say", "-v", "Daniel", clean])


def load_memory():
    try:
        with open(MEMORY_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_memory(messages):
    history = [m for m in messages if m["role"] != "system"][-MAX_HISTORY:]
    try:
        _write_private(MEMORY_FILE, history)
    except OSError:
        pass


# ---------------------------------------------------------------- main loop

BANNER = """\033[96m
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
\033[0m Just A Rather Very Intelligent System — local & free
"""

HELP = """Commands:
  /voice on|off   toggle spoken replies (macOS)
  /model <name>   switch Ollama model (e.g. /model qwen2.5:7b)
  /legal on|off   legal work mode: strict citation rules, drafting discipline
  /web on|off     allow research on trusted scholarly sites only (default off)
  /draft <desc>   produce work via draft → self-critique → revise → citation audit
  /learn <fact>   teach Jarvis something permanently
  /knowledge      show everything Jarvis has learned
  /forget         wipe the learned knowledge base
  /reset          clear conversation memory
  /help           this message
  /quit           exit
Put case files/briefs in ~/Documents/JarvisWork and say "read <filename>".
Run librarian.py to have Jarvis study books/briefs/cases on his own.
Anything else is a message to Jarvis."""


def security_check():
    """Jarvis is local-only: refuse to talk to a non-local model server."""
    host = urllib.parse.urlparse(OLLAMA_URL).hostname or ""
    if host not in ("localhost", "127.0.0.1", "::1"):
        print(f"🛑 Security: JARVIS_OLLAMA_URL points at a remote host ({host}).")
        print("   Jarvis is local-only by design. Refusing to start.")
        sys.exit(1)


def check_ollama(model):
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=5) as resp:
            tags = json.load(resp)
        names = [m["name"] for m in tags.get("models", [])]
        if not any(n == model or n.split(":")[0] == model.split(":")[0] for n in names):
            print(f"⚠️  Model '{model}' not found locally. Pulling it now (one-time download)...")
            subprocess.run(["ollama", "pull", model], check=True)
        return True
    except Exception:
        print("❌ Cannot reach Ollama at " + OLLAMA_URL)
        print("   Install it from https://ollama.com (or run ./install.sh),")
        print("   then start it with:  ollama serve")
        return False


def main():
    global LEGAL_MODE, WEB_MODE
    model = DEFAULT_MODEL
    speak = IS_MAC

    security_check()
    if not check_ollama(model):
        sys.exit(1)

    messages = [{"role": "system", "content": build_system_prompt()}] + load_memory()

    # one-shot mode: question passed as CLI args
    if len(sys.argv) > 1:
        messages.append({"role": "user", "content": " ".join(sys.argv[1:])})
        chat_turn(model, messages, speak=False)
        save_memory(messages)
        return

    print(BANNER)
    print(f" Model: {model}   Voice: {'on' if speak else 'off'}   (/help for commands)\n")

    while True:
        try:
            user = input("\033[93mYou:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nJARVIS: Powering down. Goodbye, sir.")
            break
        if not user:
            continue

        if user.startswith("/"):
            cmd, _, arg = user.partition(" ")
            if cmd == "/quit":
                print("JARVIS: Goodbye, sir.")
                break
            elif cmd == "/help":
                print(HELP)
            elif cmd == "/reset":
                messages = [{"role": "system", "content": build_system_prompt(LEGAL_MODE)}]
                save_memory(messages)
                print("JARVIS: Conversation memory wiped. A fresh start, sir.")
            elif cmd == "/web":
                WEB_MODE = arg.lower() != "off"
                messages[0]["content"] = build_system_prompt(LEGAL_MODE)
                if WEB_MODE:
                    print("JARVIS: Research access granted, sir — restricted to "
                          "trusted scholarly sources:")
                    for d in load_allowed_domains():
                        print(f"          • {d}")
                    print(f"        (add more in {DOMAINS_FILE})")
                else:
                    print("JARVIS: Web access revoked, sir. Fully offline again.")
            elif cmd == "/legal":
                LEGAL_MODE = arg.lower() != "off"
                messages[0]["content"] = build_system_prompt(LEGAL_MODE)
                if LEGAL_MODE:
                    print("JARVIS: Legal work mode engaged, sir. Strict citation "
                          "discipline in force. Do remember: I draft, a qualified "
                          "human reviews — I am not a licensed attorney.")
                else:
                    print("JARVIS: Legal mode disengaged, sir.")
            elif cmd == "/draft":
                if not arg:
                    print("JARVIS: Draft what, sir? Usage: /draft <description of the document>")
                    continue
                print("JARVIS: Very good, sir. Producing it properly — this takes three passes.")
                try:
                    final, verified, unverified, saved = multi_pass_draft(model, arg)
                except Exception as e:
                    print(f"JARVIS: The drafting run failed, sir: {e}")
                    continue
                print("\n" + final + "\n")
                print(f"JARVIS: {saved}")
                if verified:
                    print(f"        ✓ {len(verified)} citation(s) verified against loaded sources.")
                if unverified:
                    print(f"        ⚠️ {len(unverified)} citation(s) NOT found in any source — "
                          "flagged in the file. Verify before relying on them:")
                    for c in unverified:
                        print(f"           • {c}")
                if not SOURCE_DOCS:
                    print("        Note: no source documents were loaded, so no citation "
                          "could be verified. Read the case files first for best results.")
            elif cmd == "/learn":
                if arg:
                    print("JARVIS: " + tool_remember_fact(arg))
                    messages[0]["content"] = build_system_prompt(LEGAL_MODE)
                else:
                    print("JARVIS: Learn what, sir? Usage: /learn <fact>")
            elif cmd == "/knowledge":
                facts = load_knowledge()
                if facts:
                    print("JARVIS: Everything I've learned, sir:")
                    for f in facts:
                        print(f"  • {f['fact']}  ({f['learned']})")
                else:
                    print("JARVIS: I haven't been taught anything yet, sir.")
            elif cmd == "/forget":
                _write_private(KNOWLEDGE_FILE, [])
                messages[0]["content"] = build_system_prompt(LEGAL_MODE)
                print("JARVIS: Knowledge base cleared, sir.")
            elif cmd == "/voice":
                speak = arg.lower() != "off"
                print(f"JARVIS: Voice {'engaged' if speak else 'muted'}, sir.")
            elif cmd == "/model":
                if arg and check_ollama(arg):
                    model = arg
                    print(f"JARVIS: Switched to {model}, sir.")
            else:
                print(HELP)
            continue

        now = datetime.now().strftime("%A %Y-%m-%d %H:%M")
        messages.append({"role": "user", "content": f"[{now}] {user}"})
        try:
            chat_turn(model, messages, speak)
        except Exception as e:
            print(f"\nJARVIS: I'm afraid something went wrong, sir: {e}")
            messages.pop()
            continue
        save_memory(messages)
        # keep the in-RAM context bounded too
        if len(messages) > MAX_HISTORY + 1:
            messages = [messages[0]] + messages[-MAX_HISTORY:]


if __name__ == "__main__":
    main()
