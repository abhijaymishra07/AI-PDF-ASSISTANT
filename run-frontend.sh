#!/usr/bin/env bash
export PROJECT="$HOME/Desktop/Projects/PDF AI ASSISTANT/PDF ASSISTANT"
cd "$PROJECT/frontend" || exit 1
if [ ! -d node_modules ]; then
  npm install
fi
npm run dev
