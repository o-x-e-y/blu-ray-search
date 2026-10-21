# blu-ray-search

A morning routine that fetches the Blu-rays listed on Marktplaats since the last
successful run around Eindhoven, Helmond and home (`scout/fetch.py`, no login), matches them against Letterboxd (films rated 4★+, the watchlist, minus discs
already owned), and publishes the
[Blu-ray Scout](https://claude.ai/artifact/HkWBAnLZYRZ2CY8MRjuHji) page.

The instructions are in `.claude/skills/blu-ray-scout/SKILL.md`. `scout/setup.sh`
downloads `boxd` and the taste profile from the public nixos repo, so neither
the routine nor a film-list refresh needs NixOS.

## Routine settings

- **Prompt:** `Run the blu-ray-scout skill (.claude/skills/blu-ray-scout/SKILL.md).`
- **Schedule:** cron `48 4 * * *` (UTC): 06:48 Amsterdam in summer, 05:48 in
  winter.
- **Repository:** this one.
- **Connectors:** only Claude Docs and Claude Code Remote. Gmail isn't needed:
  the saved-search emails only carry a count, not the listings.
- **Network:** Custom. Add `raw.githubusercontent.com` and `www.marktplaats.nl`
  to the defaults. The defaults already cover PyPI, which
  `setup.sh` needs for `curl_cffi`.
- **Model:** Haiku. It matched as well as Sonnet on the 2026-10-16 test; switch
  to Sonnet if it misses things.

## Trash

Each ad on the page has a trash button (click twice to confirm). Trashed ids go
to the page's own database, a `trash` collection, and the page hides them
until they sell or get reserved; the trash tab lists them with a restore
button. The routine needs no part in it: a trashed ad stays tracked, so it is
never offered as new again.

## Film list

Letterboxd's Cloudflare blocks `boxd` from the routine's cloud IP, so the routine
never contacts Letterboxd and uses the `scout/films.txt` committed here. Refresh
it from a machine Letterboxd accepts:

```bash
bash scout/setup.sh && scout/.venv/bin/python scout/films.py
git commit -m "Refresh film list" scout/films.txt && git push
```

## Owned discs

`scout/films.py` leaves out every film on the Letterboxd list
[Movies I own](https://letterboxd.com/oxey/list/movies-i-own/). After adding a
disc there, refresh the film list as above.
