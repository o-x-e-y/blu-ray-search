# Matching Marktplaats Blu-ray ads against a film list

This brief is for the nationwide page (`scout/nationwide.py`) only. It is not
part of the Blu-ray Scout routine, which follows its own skill.

You are matching second-hand Blu-ray ads from Marktplaats (Dutch classifieds)
against one person's list of films they'd buy on disc. Read-only job: don't
fetch anything from the web, don't edit any file except your output file.

## Inputs

- The film list: `/home/oxey/Repos/blu-ray-search/scout/films.txt`, one film
  per line: `slug | Title (year) | rated 4.5` (a film they loved) or
  `slug | Title (year) | watchlist` (a film they want to see). Read all of it
  first (about 770 lines) and keep it in mind.
- Your ad chunks (listed in your task), one ad per line:
  `id | ad title | description` (the description is cut off around 250
  characters). Read every line of every chunk, in pieces of about 250 lines.

## Rules

- **Read every ad yourself.** Don't write a script that matches titles. It
  misses Dutch titles ("Hoe tem je een draak" = How to Train Your Dragon),
  box sets and lots that don't name every film, and it can't tell remakes apart.
- **Be permissive.** Including a doubtful match costs the person a glance;
  missing a real one costs them the disc. When an ad might be the film,
  include it and say why it's doubtful in `note`.
- **Match the film, not the words.** "Monster House" is not "Monster", "I,
  Frankenstein" is not "Frankenstein", and a Tenet ad that mentions *Inception*
  is not *Inception*. Remakes and same-titled films are different films: use
  year, director and cast to tell them apart, and note it when the ad doesn't
  say which one it is.
- **Know what's in famous sets.** A box set's contents count even when the ad
  doesn't list them, e.g. *Tarantino XX* holds all eight Tarantino films up to
  *Django Unchained*; a "Lord of the Rings trilogy" holds all three films.
- **Skip** "Gezocht"/"Gevraagd" (wanted) ads, concert and music discs, and TV
  seasons unless that series is itself on the film list.
- **Lots with unknown contents:** a collection of roughly 5+ films whose ad
  doesn't list the titles gets `"films": []`.
- **Cut-off sets:** if an ad is a set or collection and the description is
  cut off before its contents are fully listed, set `"needs_full": true` (list
  whatever films you can already match). Those ads get re-read in full later.

## Flags

Add a flag for anything that affects whether the disc plays or what they get:
`region A` (US Blu-ray, usually region-locked), `region 1` (US DVD), `DVD`
(a DVD rather than a Blu-ray), `3D only`, `4K only` (no regular Blu-ray in the
case), `damaged`. Never flag subtitles or audio language.

## Output

Write one JSON object per line to your output file, only for ads that match at
least one film on the list, unknown lots, or cut-off sets:

```
{"id": "m2453568371", "films": ["pans-labyrinth"], "films_in_listing": 1, "flags": [], "note": ""}
```

- `films`: slugs exactly as they appear in `films.txt`.
- `films_in_listing`: every film in the ad, including ones not on the list.
- `note`: short, only when there's a doubt or something worth knowing.
- `needs_full`: only when true.

Leave out ads that match nothing.

**Full descriptions** (`nl/full.txt`, the cut-off sets re-read in full): never
set `needs_full`, and write a line for every ad, so each earlier partial match
gets replaced. When an ad holds none of the films, give it `"films": []` and a
note saying what's in it. When its contents still aren't listed, also set
`"unknown_contents": true`; those stay on the page as lots to look into, the
rest are dropped. When done, reply with one line: how many ads
you read and how many lines you wrote. Nothing else.
