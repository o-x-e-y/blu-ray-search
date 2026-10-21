#!/usr/bin/env python3
"""Write films.txt: every film worth buying on disc, one per line.

    slug | Title (year) | rated 4.5
    slug | Title (year) | watchlist

Films rated 4.0 or higher plus the watchlist, minus anything on the owned list.
Run it on the user's machine: Letterboxd's Cloudflare blocks cloud IPs.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
USER = "oxey"
OWNED_LIST = "movies-i-own"


def boxd(*args: str) -> list[dict]:
    out = subprocess.run(
        [str(HERE / ".venv/bin/python"), str(HERE / "vendor/boxd.py"), "--json", *args],
        env={**os.environ, "BOXD_USER": USER},
        capture_output=True,
        text=True,
    )
    if out.returncode:
        sys.exit(f"boxd {' '.join(args)} failed: {out.stderr.strip()}")
    return json.loads(out.stdout)["films"]


def main() -> None:
    owned = {f["slug"] for f in boxd("list", OWNED_LIST)}
    lines = []
    for film in boxd("ratings"):
        if (film["rating"] or 0) >= 4 and film["slug"] not in owned:
            lines.append(f"{film['slug']} | {film['title']} ({film['year']}) | rated {film['rating']}")
    for film in boxd("watchlist"):
        if film["slug"] not in owned:
            lines.append(f"{film['slug']} | {film['title']} ({film['year']}) | watchlist")
    (HERE / "films.txt").write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} films written")


if __name__ == "__main__":
    main()
