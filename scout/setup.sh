#!/usr/bin/env bash
# Fetches boxd and the taste profile from the public nixos repo, then installs
# boxd's one dependency. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

RAW=https://raw.githubusercontent.com/o-x-e-y/nixos/main/home/programs
mkdir -p vendor
curl -fsSL "$RAW/boxd/boxd.py" -o vendor/boxd.py
curl -fsSL "$RAW/claude-code/boxd/taste.md" -o vendor/taste.md

[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install --quiet curl_cffi
