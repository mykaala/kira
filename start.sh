#!/usr/bin/env bash
# Kira: start everything needed to play (backend API + web app), then open the browser. Ctrl+C stops it all.
#   ./start.sh          real AI players (needs backend/.env with OPENAI_API_KEY)
#   ./start.sh --fake   free scripted AI players, no key needed
# Ports start at 8000 (API) and 5173 (web); if something else is already using one, the next free port is used.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
FAKE=0
[ "${1:-}" = "--fake" ] && FAKE=1

free_port() {
  local p=$1
  while lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; do p=$((p + 1)); done
  echo "$p"
}

# an old Python 2.7 sits first on PATH here, so name 3.14 explicitly
PY="$(command -v python3.14 || true)"
[ -z "$PY" ] && PY=/opt/homebrew/opt/python@3.14/bin/python3.14
if [ ! -x "$PY" ]; then
  echo "Python 3.14 not found. Install it (brew install python@3.14) and run this again." >&2
  exit 1
fi

if [ ! -d "$ROOT/backend/.venv" ]; then
  echo "Installing the backend (first run only)…"
  (cd "$ROOT/backend" && uv sync --python "$PY")
fi
if [ ! -d "$ROOT/web/node_modules" ]; then
  echo "Installing the web app (first run only)…"
  # the global npm cache is root-owned on this machine, so use a private one
  (cd "$ROOT/web" && npm install --cache "${TMPDIR:-/tmp}/kira-npm-cache")
fi
if [ "$FAKE" = 0 ] && ! grep -qs "OPENAI_API_KEY=." "$ROOT/backend/.env"; then
  echo "No OPENAI_API_KEY in backend/.env. Add it, or run ./start.sh --fake to play with scripted AIs." >&2
  exit 1
fi

API_PORT=$(free_port 8000)
WEB_PORT=$(free_port 5173)
PIDS=()
kill_tree() {  # a process and everything it started (uv -> uvicorn, npx -> vite)
  local child
  for child in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$child"; done
  kill "$1" 2>/dev/null || true
}
stop() {
  trap - INT TERM EXIT
  echo
  echo "Stopping Kira…"
  for pid in "${PIDS[@]}"; do kill_tree "$pid"; done
  exit 0
}
trap stop INT TERM EXIT

if [ "$FAKE" = 1 ]; then
  (cd "$ROOT/backend" && FAKE_LLM=1 exec uv run uvicorn server.app:app --port "$API_PORT" --timeout-graceful-shutdown 2) &
else
  (cd "$ROOT/backend" && exec uv run uvicorn server.app:app --port "$API_PORT" --timeout-graceful-shutdown 2) &
fi
PIDS+=($!)
(cd "$ROOT/web" && KIRA_API="http://localhost:$API_PORT" exec npx vite --port "$WEB_PORT" --strictPort --clearScreen false) &
PIDS+=($!)

URL="http://localhost:$WEB_PORT"
for _ in $(seq 1 60); do
  curl -s "http://localhost:$API_PORT/api/cast" >/dev/null && curl -s "$URL" >/dev/null && break
  sleep 0.5
done
echo
echo "Kira is running at $URL  ($([ "$FAKE" = 1 ] && echo "scripted AIs" || echo "real AI players"); API on port $API_PORT)"
echo "Press Ctrl+C to stop."
[ -z "${KIRA_NO_OPEN:-}" ] && { open "$URL" 2>/dev/null || true; }  # KIRA_NO_OPEN=1: don't open a browser
wait
