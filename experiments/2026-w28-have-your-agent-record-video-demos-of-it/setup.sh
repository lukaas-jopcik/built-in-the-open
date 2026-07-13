#!/usr/bin/env bash
# Creates a repo-local venv and installs everything record.sh needs:
# shot-scraper (pip) + Playwright's Chromium + Playwright's bundled ffmpeg.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PY=python3

if [ ! -d .venv ]; then
  if ! "$PY" -m venv .venv 2>/tmp/venv_err.$$; then
    cat /tmp/venv_err.$$ >&2
    # Debian/Ubuntu split the venv module into its own package; try to
    # self-heal if we can, since a stranger shouldn't have to know that.
    if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
      echo "Attempting to install the missing python3-venv package..." >&2
      PYVER=$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
      apt-get update -qq && apt-get install -y -qq "python${PYVER}-venv" python3-venv
      "$PY" -m venv .venv
    else
      rm -f /tmp/venv_err.$$
      exit 1
    fi
  fi
  rm -f /tmp/venv_err.$$
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet shot-scraper

# Downloads Chromium + a matching ffmpeg build into Playwright's cache dir.
.venv/bin/shot-scraper install

# shot-scraper's `video --mp4` flag shells out to a system `ffmpeg` binary
# (separate from the one Playwright just downloaded) to transcode WebM->MP4.
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
    echo "ffmpeg not found on PATH; installing it..." >&2
    apt-get update -qq && apt-get install -y -qq ffmpeg
  fi
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERROR: ffmpeg is required (for MP4 conversion) but was not found and" >&2
  echo "could not be auto-installed. Please install ffmpeg and re-run ./setup.sh" >&2
  exit 1
fi

echo "Setup complete:"
.venv/bin/shot-scraper --version
ffmpeg -version | head -1
