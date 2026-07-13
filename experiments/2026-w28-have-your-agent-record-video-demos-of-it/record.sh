#!/usr/bin/env bash
# Serves demo/app.html locally, drives it with shot-scraper per demo/storyboard.yml,
# and writes output/demo.mp4. Idempotent: safe to re-run, overwrites prior output.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

SHOT_SCRAPER=.venv/bin/shot-scraper

if [ ! -x "$SHOT_SCRAPER" ]; then
  echo "ERROR: $SHOT_SCRAPER not found. Run ./setup.sh first." >&2
  exit 1
fi

mkdir -p output

# Prefer port 8934 (matches the checked-in storyboard), but fall back to a
# kernel-assigned free port if something else already has it bound.
PORT=8934
if ! python3 -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(('127.0.0.1', $PORT))
except OSError:
    sys.exit(1)
s.close()
" 2>/dev/null; then
  PORT=$(python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('127.0.0.1', 0))
print(s.getsockname()[1])
s.close()
")
  echo "Port 8934 busy, falling back to port $PORT" >&2
fi

SERVER_PID=""
cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

HTTP_LOG=/tmp/record_http.$$
python3 -m http.server "$PORT" --directory demo >"$HTTP_LOG" 2>&1 &
SERVER_PID=$!

# Wait for the server to actually accept connections instead of a fixed sleep,
# and fail loudly (instead of silently recording a blank page) if it never does.
BOUND=0
for i in $(seq 1 50); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "ERROR: HTTP server (pid $SERVER_PID) exited before serving. Log:" >&2
    cat "$HTTP_LOG" >&2
    rm -f "$HTTP_LOG"
    exit 1
  fi
  if curl -s -o /dev/null "http://localhost:$PORT/app.html"; then
    BOUND=1
    break
  fi
  sleep 0.1
done
rm -f "$HTTP_LOG"

if [ "$BOUND" != "1" ]; then
  echo "ERROR: HTTP server never responded on http://localhost:$PORT/app.html after 5s." >&2
  exit 1
fi

# demo/storyboard.yml hardcodes the preferred port; substitute in the actual
# bound port (usually identical, only differs on the fallback path above).
GENERATED_STORYBOARD=output/.storyboard.generated.yml
sed "s/localhost:8934/localhost:$PORT/" demo/storyboard.yml > "$GENERATED_STORYBOARD"

rm -f output/demo.mp4 output/demo.webm

"$SHOT_SCRAPER" video "$GENERATED_STORYBOARD" --mp4 -o output/demo.webm
rm -f "$GENERATED_STORYBOARD" output/demo.webm  # keep only the requested demo.mp4, no clutter

DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 output/demo.mp4)
DURATION_S=$(printf '%.1f' "$DURATION")

cat > output/caption.md <<EOF
🎬 Watched my coding agent record its own product demo end-to-end — no screen recorder, no human clicking through the UI. Just a script driving a headless browser and saving the video. output/demo.mp4 (${DURATION_S}s)
EOF

echo "Recorded output/demo.mp4 (${DURATION_S}s) and output/caption.md"
