#!/usr/bin/env bash
export PROJECT="$HOME/Desktop/Projects/PDF AI ASSISTANT/PDF ASSISTANT"
cd "$PROJECT" || exit 1
source .venv/bin/activate
export PYTHONPATH="${PWD}"
uvicorn backend.app.main:app --reload --port 8000
