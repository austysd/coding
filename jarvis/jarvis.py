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
WORK_DIR = os.path.expanduser("~/Documents/JarvisWork")
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


def tool_read_document(filename):
    path = _safe_workpath(filename)
    if not path or not os.path.isfile(path):
        return f"No such document in {WORK_DIR}."
    with open(path) as f:
        return f.read()[:20000]


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
    "set_timer": tool_set_timer,
}


def build_system_prompt():
    """System prompt plus everything Jarvis has learned so far."""
    facts = load_knowledge()
    if not facts:
        return SYSTEM_PROMPT
    learned = "\n".join(f"- {f['fact']}" for f in facts)
    return SYSTEM_PROMPT + "\nThings you have learned about the user:\n" + learned

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
            gen = ollama_chat(model, messages, tools=TOOLS if supports_tools else None)
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
                messages[0]["content"] = build_system_prompt()
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
  /learn <fact>   teach Jarvis something permanently
  /knowledge      show everything Jarvis has learned
  /forget         wipe the learned knowledge base
  /reset          clear conversation memory
  /help           this message
  /quit           exit
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
                messages = [{"role": "system", "content": build_system_prompt()}]
                save_memory(messages)
                print("JARVIS: Conversation memory wiped. A fresh start, sir.")
            elif cmd == "/learn":
                if arg:
                    print("JARVIS: " + tool_remember_fact(arg))
                    messages[0]["content"] = build_system_prompt()
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
                messages[0]["content"] = build_system_prompt()
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
