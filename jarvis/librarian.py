#!/usr/bin/env python3
"""
Jarvis's Librarian — autonomous study, so Jarvis learns without being asked.

What it does on each run:
  1. (--web) Fetches real court opinions from CourtListener's free public API
     for the topics you list in ~/Documents/JarvisLibrary/topics.txt,
     saving them into the library folder.
  2. Studies every new or changed file in ~/Documents/JarvisLibrary/
     (books, legal briefs, case files — .txt .md .pdf .docx .rtf):
     the local model reads each one and writes structured study notes.
  3. Stores the notes + text in Jarvis's library (~/.jarvis_library.json),
     which Jarvis searches during conversation and uses to verify citations.

Usage:
  python3 librarian.py                # study new files in the library folder
  python3 librarian.py --web          # also fetch new material from the web first
  python3 librarian.py --schedule     # install a nightly 2am study session (launchd)
  python3 librarian.py --status       # show what Jarvis has studied

Drop files into ~/Documents/JarvisLibrary/ and Jarvis studies them on the
next run — no prompting needed once the schedule is installed.
"""

import json
import os
import plistlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request

from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jarvis import (  # noqa: E402
    DEFAULT_MODEL,
    IS_MAC,
    LIBRARY_FILE,
    _extract_text,
    _write_private,
    load_library,
    ollama_chat,
    security_check,
    tool_remember_fact,
)

LIBRARY_DIR = os.path.expanduser("~/Documents/JarvisLibrary")
TOPICS_FILE = os.path.join(LIBRARY_DIR, "topics.txt")
PLIST_PATH = os.path.expanduser("~/Library/LaunchAgents/com.jarvis.librarian.plist")
COURTLISTENER = "https://www.courtlistener.com/api/rest/v4"
MAX_STUDY_CHARS = 24000  # what fits comfortably in a small local model's context

STUDY_PROMPT = """\
You are J.A.R.V.I.S. studying a document to build your permanent expertise.
Produce structured study notes with exactly these sections:

SUMMARY: 3-5 sentences on what this document is and says.
KEY POINTS: the most important facts, holdings, or arguments (bullet list).
CITATIONS FOUND: every legal citation that appears VERBATIM in the text,
copied character-for-character (or "none").
LESSONS: 2-3 things you learned that will make your future work better.

Rules: only state what is actually in the document. Never add outside
knowledge, never invent citations. If the text is truncated, note that.
"""


def studyable(name):
    return not name.startswith(".") and os.path.splitext(name)[1].lower() in (
        ".txt", ".md", ".text", ".pdf", ".docx", ".doc", ".rtf", ".html",
    )


def study_file(model, path):
    """Have the local model read one document and produce study notes."""
    text = _extract_text(path)
    truncated = len(text) > MAX_STUDY_CHARS
    excerpt = text[:MAX_STUDY_CHARS]
    messages = [
        {"role": "system", "content": STUDY_PROMPT},
        {"role": "user", "content": f"Document: {os.path.basename(path)}"
         + (" (truncated excerpt)" if truncated else "") + "\n\n" + excerpt},
    ]
    notes = ""
    for chunk, _ in ollama_chat(model, messages, tools=None, stream=True):
        notes += chunk
    return notes.strip(), text


def ingest(model):
    """Study every new or changed file in the library folder."""
    os.makedirs(LIBRARY_DIR, exist_ok=True)
    library = load_library()
    studied = 0
    for name in sorted(os.listdir(LIBRARY_DIR)):
        path = os.path.join(LIBRARY_DIR, name)
        if not os.path.isfile(path) or not studyable(name):
            continue
        mtime = os.path.getmtime(path)
        if name in library and library[name].get("mtime") == mtime:
            continue  # already studied this version
        print(f"📖 Studying: {name}")
        try:
            notes, text = study_file(model, path)
        except Exception as e:
            print(f"   failed: {e}")
            continue
        library[name] = {
            "notes": notes,
            "text": text[:100000],  # kept for citation verification
            "mtime": mtime,
            "studied": datetime.now().isoformat(timespec="minutes"),
        }
        _write_private(LIBRARY_FILE, library)
        summary = notes.split("\n")[0][:150] if notes else name
        tool_remember_fact(f"I have studied '{name}' in my library. {summary}")
        studied += 1
    return studied


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-librarian/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def web_study():
    """Fetch fresh court opinions for the user's topics from CourtListener.

    CourtListener (Free Law Project, courtlistener.com) publishes real,
    public-domain court opinions — a trustworthy source, unlike scraping
    random websites.
    """
    if not os.path.isfile(TOPICS_FILE):
        os.makedirs(LIBRARY_DIR, exist_ok=True)
        with open(TOPICS_FILE, "w") as f:
            f.write("# One study topic per line; Jarvis fetches real court opinions\n"
                    "# about each topic on every --web run. Examples:\n"
                    "# breach of contract\n"
                    "# landlord tenant eviction\n")
        print(f"Created {TOPICS_FILE} — add topics, then re-run with --web.")
        return 0

    with open(TOPICS_FILE) as f:
        topics = [t.strip() for t in f if t.strip() and not t.startswith("#")]
    if not topics:
        print("No topics in topics.txt yet; skipping web study.")
        return 0

    fetched = 0
    for topic in topics:
        print(f"🌐 Searching case law: {topic}")
        try:
            query = urllib.parse.urlencode({"q": topic, "type": "o", "order_by": "score desc"})
            results = _get_json(f"{COURTLISTENER}/search/?{query}").get("results", [])[:2]
            for hit in results:
                case = hit.get("caseName") or "unknown-case"
                slug = re.sub(r"[^a-z0-9]+", "-", case.lower()).strip("-")[:60]
                dest = os.path.join(LIBRARY_DIR, f"case-{slug}.txt")
                if os.path.exists(dest):
                    continue
                opinion_id = (hit.get("opinions") or [{}])[0].get("id")
                if not opinion_id:
                    continue
                op = _get_json(f"{COURTLISTENER}/opinions/{opinion_id}/?fields=plain_text")
                text = op.get("plain_text", "")
                if len(text) < 500:
                    continue
                header = (f"{case}\nCourt: {hit.get('court', '?')}   "
                          f"Date: {hit.get('dateFiled', '?')}\n"
                          f"Citation: {'; '.join(hit.get('citation') or []) or 'unreported'}\n"
                          f"Source: courtlistener.com (topic: {topic})\n\n")
                with open(dest, "w") as f:
                    f.write(header + text)
                print(f"   saved: {os.path.basename(dest)}")
                fetched += 1
        except Exception as e:
            print(f"   web unavailable or query failed ({e}); continuing offline.")
    return fetched


def install_schedule():
    """Install a launchd job: study session every night at 2:00 AM."""
    if not IS_MAC:
        print("Scheduling via launchd is macOS-only. Use cron elsewhere.")
        return
    python = sys.executable or "/usr/bin/python3"
    script = os.path.abspath(__file__)
    plist = {
        "Label": "com.jarvis.librarian",
        "ProgramArguments": [python, script, "--web"],
        "StartCalendarInterval": {"Hour": 2, "Minute": 0},
        "StandardOutPath": os.path.expanduser("~/Library/Logs/jarvis-librarian.log"),
        "StandardErrorPath": os.path.expanduser("~/Library/Logs/jarvis-librarian.log"),
    }
    os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)
    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist, f)
    subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
    subprocess.run(["launchctl", "load", PLIST_PATH], check=True)
    print("✓ Nightly study session installed (2:00 AM, logs in ~/Library/Logs/).")
    print("  Jarvis will now read and learn on his own. Remove with:")
    print(f"  launchctl unload {PLIST_PATH} && rm {PLIST_PATH}")


def status():
    library = load_library()
    if not library:
        print("Jarvis hasn't studied anything yet.")
        print(f"Drop files into {LIBRARY_DIR} and run: python3 librarian.py")
        return
    print(f"Jarvis has studied {len(library)} document(s):")
    for name, entry in sorted(library.items()):
        print(f"  📚 {name}  (studied {entry.get('studied', '?')})")


def main():
    args = sys.argv[1:]
    if "--status" in args:
        status()
        return
    if "--schedule" in args:
        install_schedule()
        return

    security_check()
    if "--web" in args:
        web_study()

    print(f"Checking {LIBRARY_DIR} for new material...")
    n = ingest(DEFAULT_MODEL)
    print(f"Done — studied {n} new document(s)." if n else "Nothing new to study.")


if __name__ == "__main__":
    main()
