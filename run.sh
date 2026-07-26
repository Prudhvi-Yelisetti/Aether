#!/usr/bin/env bash
#
# run.sh — starts Ollama, the Aether backend, and the frontend dev server
# together for local testing. Run it, wait for both URLs to print, test
# in the browser, and press Ctrl+C when done — everything this script
# started gets cleaned up.
#
# Usage:
#   ./run.sh
#
# Notes learned the hard way while building this (see STATUS.md/
# HANDOFF.md for the full session this came out of):
#   - Backend defaults to port 8000. If something else is already
#     listening there (this machine sometimes runs a second, unrelated
#     project on 8000), the script uses 8010 instead and points the
#     frontend at it automatically via REACT_APP_API_URL — no manual
#     config needed either way.
#   - Ollama is only stopped on exit if THIS script had to start it. If
#     it was already running before you ran this script, it's left
#     running afterward too — other things on this machine may depend
#     on it.
#   - npm's dev server doesn't always die cleanly when you kill the
#     `npm start` process alone (the underlying webpack process can
#     survive it) — cleanup also kills by port as a fallback.
#   - Cleanup was tested via SIGTERM (`kill <pid>`) and confirmed to stop
#     everything cleanly, including the port-fallback logic. Ctrl+C in a
#     real interactive terminal sends SIGINT the normal way and should
#     work the same — this trap is registered for INT and TERM alike —
#     but that specific path wasn't separately verified with a real
#     terminal session. If Ctrl+C ever doesn't stop things, `kill <pid>`
#     (SIGTERM, the default) on this script's own process is a confirmed
#     working fallback.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
FRONTEND_PORT=3000

BACKEND_PORT=8000
if lsof -i:"$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "Port $BACKEND_PORT is already in use by something else — using 8010 for Aether's backend instead."
  BACKEND_PORT=8010
fi

PIDS=()
STARTED_OLLAMA=0

cleanup() {
  echo ""
  echo "Stopping..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  # Fallback: npm start's actual dev server process can survive killing
  # the npm wrapper alone. Clean up by port too, just in case.
  lsof -ti:"$FRONTEND_PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
  lsof -ti:"$BACKEND_PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
  if [ "$STARTED_OLLAMA" -eq 1 ]; then
    lsof -ti:11434 2>/dev/null | xargs -r kill 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  echo "Stopped."
}
trap cleanup EXIT INT TERM

# -------- Ollama --------
if ! curl -s -m 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Starting Ollama..."
  ollama serve > /tmp/aether_ollama_run.log 2>&1 &
  PIDS+=($!)
  STARTED_OLLAMA=1
  for _ in $(seq 1 10); do
    curl -s -m 2 http://localhost:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi

if ! curl -s -m 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama did not come up — check /tmp/aether_ollama_run.log"
  exit 1
fi
echo "Ollama is up."

# -------- Backend --------
if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "Backend venv not found at $BACKEND_DIR/.venv — set it up first (see STATUS.md)."
  exit 1
fi

echo "Starting backend on port $BACKEND_PORT..."
(cd "$BACKEND_DIR" && .venv/bin/uvicorn main:app --reload --port "$BACKEND_PORT") \
  > /tmp/aether_backend_run.log 2>&1 &
PIDS+=($!)

for _ in $(seq 1 15); do
  curl -s -m 2 "http://localhost:$BACKEND_PORT/" >/dev/null 2>&1 && break
  sleep 1
done
if ! curl -s -m 2 "http://localhost:$BACKEND_PORT/" >/dev/null 2>&1; then
  echo "Backend did not come up — check /tmp/aether_backend_run.log"
  exit 1
fi
echo "Backend is up at http://localhost:$BACKEND_PORT"

# -------- Frontend --------
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies (first run only, this can take a minute)..."
  (cd "$FRONTEND_DIR" && npm install)
fi

echo "Starting frontend..."
(cd "$FRONTEND_DIR" && \
  REACT_APP_API_URL="http://127.0.0.1:$BACKEND_PORT" BROWSER=none npm start) \
  > /tmp/aether_frontend_run.log 2>&1 &
PIDS+=($!)

echo ""
echo "Aether is running:"
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo ""
echo "Logs: /tmp/aether_backend_run.log, /tmp/aether_frontend_run.log, /tmp/aether_ollama_run.log"
echo "Press Ctrl+C to stop everything this script started."

wait
