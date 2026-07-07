#!/bin/bash
# One-time setup for J.A.R.V.I.S. on macOS.
# Installs Ollama (the free local model runner) and downloads a model.
set -e

MODEL="${JARVIS_MODEL:-llama3.1:8b}"

echo "── J.A.R.V.I.S. setup ─────────────────────────────"

# 1. Ollama
if command -v ollama >/dev/null 2>&1; then
    echo "✓ Ollama already installed"
else
    echo "→ Installing Ollama..."
    if command -v brew >/dev/null 2>&1; then
        brew install ollama
    else
        echo "  Homebrew not found. Download Ollama from https://ollama.com/download"
        echo "  then re-run this script."
        exit 1
    fi
fi

# 2. Make sure the server is running
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "→ Starting Ollama server in the background..."
    nohup ollama serve >/dev/null 2>&1 &
    sleep 3
fi

# 3. Pull the model (one-time ~5GB download; runs fully offline afterwards)
echo "→ Downloading model $MODEL (skips if already present)..."
ollama pull "$MODEL"

echo ""
echo "── Done! Start your assistant with: ──────────────"
echo "   python3 jarvis.py"
