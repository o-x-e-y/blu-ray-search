# blu-ray-search

A morning routine that fetches the Blu-rays listed on Marktplaats in the last
day around Eindhoven, Helmond and home (`scout/fetch.py`, no login), matches them against Letterboxd (films rated 4★+, the watchlist, minus discs
already owned), and publishes the
[Blu-ray Scout](https://claude.ai/artifact/HkWBAnLZYRZ2CY8MRjuHji) page.

The instructions are in `.claude/skills/blu-ray-scout/SKILL.md`. `scout/setup.sh`
downloads `boxd` from the public nixos repo, so the routine doesn't need NixOS.

## Routine settings

- **Prompt:** `Run the blu-ray-scout skill.`
- **Schedule:** daily at 06:48 Europe/Amsterdam. Runs on the hour can start a
  few minutes late.
- **Repository:** this one.
- **Connectors:** none. The saved-search emails only carry a count, not the
  listings.
- **Network:** Custom. Add `letterboxd.com`, `raw.githubusercontent.com` and
  `www.marktplaats.nl` to the defaults. The defaults already cover PyPI, which
  `setup.sh` needs for `curl_cffi`.
- **Model:** Sonnet. Haiku matched as well on the 2026-10-16 test and is worth
  trying.

## Owned discs

Once the Letterboxd list of owned discs exists, set `OWNED_LIST` in
`scout/films.py` to its slug. That needs the `boxd list` command pushed to the
nixos repo first.
