# blu-ray-search

A routine, run on demand, that fetches the Blu-rays listed on Marktplaats since
the last published run around Eindhoven, Helmond and home (`scout/fetch.py`, no login), matches them against Letterboxd (films rated 4★+, the watchlist, minus discs
already owned), and publishes the
[Blu-ray Scout](https://claude.ai/artifact/HkWBAnLZYRZ2CY8MRjuHji) page.

The instructions are in `.claude/skills/blu-ray-scout/SKILL.md`. `scout/setup.sh`
downloads `boxd` and the taste profile from the public nixos repo, so neither
the routine nor a film-list refresh needs NixOS.

## Routine settings

- **Prompt:** `Run the blu-ray-scout skill (.claude/skills/blu-ray-scout/SKILL.md).`
- **Schedule:** none. The page's "rerun scout" link opens the routine, where
  "Run now" starts a fresh list. A gap of any length is fine: every ad posted
  since the last published run counts as new and gets a "new" badge.
- **Repository:** this one.
- **Connectors:** only Claude Docs and Claude Code Remote. Gmail isn't needed:
  the saved-search emails only carry a count, not the listings.
- **Network:** Custom. Add `raw.githubusercontent.com` and `www.marktplaats.nl`
  to the defaults. The defaults already cover PyPI, which
  `setup.sh` needs for `curl_cffi`.
- **Model:** Haiku. It matched as well as Sonnet on the 2026-10-16 test; switch
  to Sonnet if it misses things.

## 4K players

Each run also searches the whole country for Blu-ray players (two searches,
"4k" and "uhd", in the Blu-ray player category) and shows the ones that name a
4K model on a "4k players" tab. The pattern in `scout/fetch.py` looks for model
names (Sony UBP-X, Panasonic DP-UB, LG UBK, Oppo UDP and so on) rather than
"4K", because players that only upscale to 4K, like the Panasonic DMP-BDT180,
can't play 4K discs. Reserved and "gezocht" ads are left out.

## Trash

Each ad on the page has a trash button. Trashed ids go to the page's own
database, a `trash` collection, and the page hides them until they sell or get
reserved. The trash tab lists them, most recently trashed first, each with a
restore button. Neither button asks for confirmation, since a mistake is one
click to undo. The routine needs no part in it: a trashed ad stays tracked, so it is
never offered as new again.

## Changing the page

A change to `scout/template.html` alone doesn't need a scout run, which costs
Marktplaats requests. Commit and push it so later runs keep it, then patch the
same blocks into the live page and republish it to the same URL without
`capabilities`, so the trash database stays.

## Film list

Letterboxd's Cloudflare blocks `boxd` from the routine's cloud IP, so the routine
never contacts Letterboxd and uses the `scout/films.txt` committed here. Refresh
it from a machine Letterboxd accepts:

```bash
bash scout/setup.sh && scout/.venv/bin/python scout/films.py
git commit -m "Refresh film list" scout/films.txt && git push
```

The page stores the film list it was matched against, so the next run also
checks every ad it has seen before against the films added since, and drops
earlier finds whose films have left the list.

## Nationwide page

`scout/nationwide.py` builds a separate page,
[Blu-ray Scout NL](https://claude.ai/artifact/UERvaf3zJKw78nA577eTGM), from
every Blu-ray on Marktplaats, run by hand rather than by the routine. It only
reads `films.txt` and `render.py`/`template.html`, and keeps its own files in
the gitignored `scout/nl/`, so it never touches the routine's `listings.json`,
`results.json` or page.

```bash
scout/.venv/bin/python scout/nationwide.py fetch    # ~1,300 search requests, ~45 minutes, cached
# one agent per scout/nl/chunk-*.txt, following scout/nationwide-brief.md
scout/.venv/bin/python scout/nationwide.py merge
scout/.venv/bin/python scout/nationwide.py full     # one page per cut-off set
# one agent on scout/nl/full.txt, then merge again
scout/.venv/bin/python scout/nationwide.py render
```

Haiku matches well enough for this and costs far less than Sonnet on 40
chunks of 1,000 ads.

## Owned discs

`scout/films.py` leaves out every film on the Letterboxd list
[Movies I own](https://letterboxd.com/oxey/list/movies-i-own/). After adding a
disc there, refresh the film list as above.

## Wanted for someone else

`scout/wanted.txt` adds films that are neither rated 4★+ nor on the watchlist,
such as a friend's favourite, one per line in the `films.txt` format with any
tag (`the-life-of-chuck | The Life of Chuck (2024) | for a friend`). Refresh the
film list after editing it.
