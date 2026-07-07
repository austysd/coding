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
- 🔊 **Speak replies out loud** using your Mac's built-in voice (`/voice off` to mute)
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
| `/voice on\|off` | toggle spoken replies |
| `/model <name>` | switch models, e.g. `/model qwen2.5:7b` |
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
              ├─ tools: open apps/sites, timers, system stats, documents
              ├─ voice: macOS `say`
              ├─ memory: ~/.jarvis_memory.json        (conversation)
              ├─ knowledge: ~/.jarvis_knowledge.json  (learned facts)
              └─ work: ~/Documents/JarvisWork/        (documents he writes)
```

Everything stays on your machine. The only network use is the one-time model
download and any websites you ask Jarvis to open.
