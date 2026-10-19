---
name: blu-ray-scout
description: Daily scout of new Marktplaats Blu-ray listings, matched against the user's Letterboxd favourites and watchlist, published as the Blu-ray Scout page. Run by a scheduled routine each morning.
---

# Blu-ray Scout

The user is building a disc collection for a 4K projector because their internet
can't stream in 4K. Each morning you fetch the Blu-ray listings posted since the
last successful run within 8 km of Eindhoven (5611AC), 8 km of Helmond (5701RJ)
and 6 km of home (5735SZ), turn them into a list of discs worth picking up, and
publish it.

Nobody is watching this run, so don't ask questions. Make each call yourself and
note any doubt in the item's `note`.

## 1. Set up

```bash
bash scout/setup.sh
git log -1 --format=%cs -- scout/films.txt
```

`scout/films.txt` is the film list, one film per line: `slug | Title (year) | rated 4.5`
for films they love, `| watchlist` for films they want to see. Films already
owned are left out. The user generates it on their own machine, because
Letterboxd's Cloudflare blocks cloud IPs, so don't run `scout/films.py` or
contact Letterboxd. Mention the list's commit date (the `git log` line) in the
report.

If `setup.sh` fails or `films.txt` is missing or empty, stop and report it.
Matching against a missing list would publish a page that looks like "nothing
today".

## 2. Fetch the listings

The page lives at https://claude.ai/artifact/HkWBAnLZYRZ2CY8MRjuHji. Read it
with the Artifact tool (`action: "read"`). The result names the saved file
holding the current page; you need it here and in step 7.

```bash
scout/.venv/bin/python scout/fetch.py <saved page file>
```

This runs the three searches without logging in and writes `scout/listings.json`.
The page stores when the last published run fetched, so the searches start from
there and nothing is missed after a failed run. Listings the page already tracks
and reserved ones are left out. `listings` holds the rest, each with `id`,
`title`, `description` (cut off at 200 characters), `price` (as Marktplaats shows
it), `town`, `url` and `seller`. `listings_seen` is the number of listings in
that array. If `fetch.py` fails, stop and report the error.

If a listing is a set or collection and its description is cut off before the
contents, open that listing's own page (its `url`) to read the full description.
Besides these and the status check in `render.py` (step 7), fetch nothing else
from Marktplaats.

## 3. Match

Compare every listing against `scout/films.txt`.

- **Be permissive.** Including a doubtful match costs the user a glance;
  missing a real one costs them the disc. When a listing might be the film,
  include it and say why it's doubtful in `note`.
- **Match the film, not the words.** "Monster House" is not "Monster", "I,
  Frankenstein" is not "Frankenstein", and a Tenet ad that mentions *Inception*
  is not *Inception*. Remakes and same-titled films are different films: use
  year, director and cast to tell them apart.
- **Know what's in famous sets.** A box set's contents count even when the ad
  doesn't list them, e.g. *Tarantino XX* holds all eight Tarantino films up to
  *Django Unchained*.
- **Skip** "Gezocht" (wanted) ads, concert and music discs, and TV seasons
  unless that series is on the list.
- **Lots with unknown contents:** if a collection of roughly 5+ films doesn't
  list its titles, keep it with `"films": []` so it lands under "Collections to
  look into".

## 4. Location

**On the way** (`"detour": false`): anywhere in Eindhoven (they're there for
Fontys), Helmond including Stiphout, Brandevoort and Mierlo-Hout, Mierlo, Geldrop
and Nuenen (on their ride from Eindhoven to Helmond), and around home: Beek en
Donk, Aarle-Rixtel, Lieshout and Gemert.

**Detour** (`"detour": true`): every other town the searches catch, such as
Veldhoven, Son en Breugel, Best, Waalre, Deurne, Boekel or Erp. Keep a detour
listing only if one of these holds:
- it has a film rated 5★
- it's a set with two or more matched films
- it has a watchlist film the user would really want

For a watchlist film, judge from `scout/vendor/taste.md`: a director they
follow, the kind of film they rate highly. Write the reason in `note`, e.g.
"Lanthimos; you rated all three of his films 4.5+". Drop other detour listings.

## 5. Flags

Add a flag for anything that affects whether the disc plays or what they get,
and keep the listing. They'll rip a disc if their EU player refuses it.

- `region A`: US Blu-ray, usually region-locked
- `region 1`: US DVD
- `DVD`: a DVD rather than a Blu-ray
- `3D only`
- `4K only`: no regular Blu-ray in the case
- `damaged`

Never flag or filter on subtitles or audio language. English and Dutch are
both fine.

## 6. Write results.json

Write `scout/results.json`:

```json
{
  "date": "2026-10-17",
  "listings_seen": 41,
  "items": [
    {"id": "m2453568371", "title": "Pan's Labyrinth", "url": "https://www.marktplaats.nl/v/...",
     "town": "Helmond", "detour": false, "price": "€20",
     "films": ["pans-labyrinth"], "films_in_listing": 1, "flags": [], "note": ""}
  ]
}
```

- `films` holds slugs exactly as they appear in `films.txt`.
- `films_in_listing` counts every film in the listing, including ones not on the list.
- Leave out listings that match nothing, except unknown lots (`"films": []`).

## 7. Publish

1. Run, with the saved page file from step 2 so earlier finds carry over:
   ```bash
   scout/.venv/bin/python scout/render.py scout/results.json <saved page file>
   ```
   Give the Bash call a `timeout` of 600000, because it takes a few minutes.
   This opens every tracked listing's page once, one per second, to mark it
   available, reserved or gone, and to read when it was posted and who sells
   it. Only available listings are shown. Reserved ones stay tracked in case
   the reservation falls through, and gone ones are dropped. Problems with
   single listings go to stderr; mention them in the report.
2. Publish `scout/page.html` with the Artifact tool, `url` set to the page
   above.

Even with zero matches, still render and publish, so the page shows this
morning's date and the user can tell the run happened.

## 8. Report

End with a short summary:
- how many listings you read and how many matched
- how many earlier finds are now reserved or gone
- the best two or three finds, sets first, with town and price
- anything that went wrong, e.g. a failed search or a listing page that wouldn't load

Don't commit or push anything.
