#!/usr/bin/env bash
# Wow-shot: records demo/swarm.html (an on-brand "agent swarm" task board
# animating a queue of cards to completion) to output/real-demo.mp4.
#
# This used to record a real external site (imaketoday.com); the PRD's
# "Wow shot" direction (2026-07-06) overrides that — no third-party product,
# no external network dependency for the payoff shot, on-brand original demo
# instead. Structure mirrors record.sh (port fallback, bind check, no clutter).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

SHOT_SCRAPER=.venv/bin/shot-scraper
if [ ! -x "$SHOT_SCRAPER" ]; then
  echo "ERROR: $SHOT_SCRAPER not found. Run ./setup.sh first." >&2
  exit 1
fi

mkdir -p output

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

HTTP_LOG=/tmp/real_record_http.$$
python3 -m http.server "$PORT" --directory demo >"$HTTP_LOG" 2>&1 &
SERVER_PID=$!

BOUND=0
for i in $(seq 1 50); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "ERROR: HTTP server (pid $SERVER_PID) exited before serving. Log:" >&2
    cat "$HTTP_LOG" >&2
    rm -f "$HTTP_LOG"
    exit 1
  fi
  if curl -s -o /dev/null "http://localhost:$PORT/swarm.html"; then
    BOUND=1
    break
  fi
  sleep 0.1
done
rm -f "$HTTP_LOG"

if [ "$BOUND" != "1" ]; then
  echo "ERROR: HTTP server never responded on http://localhost:$PORT/swarm.html after 5s." >&2
  exit 1
fi

GENERATED_STORYBOARD=output/.real-storyboard.generated.yml
sed "s/localhost:8934/localhost:$PORT/" demo/real-storyboard.yml > "$GENERATED_STORYBOARD"

rm -f output/real-demo.mp4 output/real-demo.webm

"$SHOT_SCRAPER" video "$GENERATED_STORYBOARD" --mp4 -o output/real-demo.webm
rm -f "$GENERATED_STORYBOARD" output/real-demo.webm

DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 output/real-demo.mp4)
DURATION_S=$(printf '%.1f' "$DURATION")
echo "Recorded output/real-demo.mp4 (${DURATION_S}s)"

python3 -c "
d = $DURATION
import sys
if not (8 <= d <= 20):
    print(f'WARNING: real-demo.mp4 duration {d:.2f}s is outside the 8-20s target window', file=sys.stderr)
"
