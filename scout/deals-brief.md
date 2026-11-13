# Deals brief

Build a **deals page** from the nationwide Marktplaats data. It lists about 30
of the cheapest ways to get films off the user's list. A deal is one ad, or
several ads from the same seller sent in one parcel. The data is already on
disk, so this needs **no new Marktplaats searches**.

The user has a 5-hour usage limit and wants token use and requests kept low.
Script everything that can be scripted, and save model judgement for the
short list.

## Inputs

These were written by the 2026-11-13 run. Read them; don't change them.

- `scout/nl/results.json`: the merged items (id, films, note, needs_full,
  unknown_contents and the ad fields).
- `scout/nl/chunk-*.txt` and `scout/nl/full.txt`: the ad text, one ad per line
  in the form `id | title | description`. `full.txt` has full descriptions for
  ads whose search snippet was cut off.
- `scout/nl/pages-<date>/`: the cached raw search-API pages.
- `scout/films.txt`: `slug | title | tag`. The user has uncommitted changes
  here, so never edit, stage or commit it.
- `scout/nationwide.py`: the `render` step already reads price, place and
  distance. Reuse its helpers and its page style; don't write new ones.

Start by looking at one item in `results.json` and one cached page to learn
the field names. You need the following, and **each has a fallback**:

| need | where | if missing |
|---|---|---|
| asking price and price type (fixed, bid, "zie omschrijving", free) | results.json | cached pages |
| seller id and seller name | results.json | cached pages (the API's `sellerInformation`) |
| delivery options (shipping or pickup only) | results.json | cached pages; if absent everywhere, assume shipping and say so on the page |
| place and distance | results.json | n/a, already there |

Only ask the user if seller ids are missing from both, since bundling depends
on them. Don't refetch the ads to get them.

## Cost model

- **Shipping is €3 per parcel**, so one seller's ads share a single €3.
- **Delivered cost** of a deal = sum of asking prices + €3.
- **Budget** of a deal = the sum of a threshold for each matched film:
  - €4 for a regular Blu-ray
  - €12 for a 4K UHD edition

  The thresholds apply to the delivered cost per film, shipping included. A
  single €1 Blu-ray just makes it (€4 delivered). So do two €2.50 Blu-rays
  from one seller ((5 + 3) / 2 = €4 each). This is how bundles become
  cheaper.
- **Score** = delivered cost ÷ budget. Lower is better, and a deal qualifies
  at a score of 1.0 or less.
- **Discs not on the list are worth nothing.** A €10 lot holding 8 discs, two
  of them on the list, costs €6.50 per film.
- **Price types:**
  - Free counts as €0.
  - A bid ad ("bieden" or "vanaf") counts at its asking price, tagged **bid**.
  - "Zie omschrijving" uses the price written in the description, or the ad
    is skipped if there is none.
  - A price range from the fetch's price filters isn't a price; use the ad's
    own price.
- **Per-film format:** use the edition the ad sells. A lot that mixes formats
  gets a mixed budget. If the format is unclear, count the film as a Blu-ray.
- **Pickup:** the free pickup zones are Eindhoven, Helmond, Mierlo and
  Stiphout. Ads there keep the €3 in the score but get a "pick up free" tag.
  A pickup-only ad outside those zones and more than 30 km away is dropped.

## Bundling

Group the qualifying candidate ads by seller. Within each seller:

1. Sort the ads by their score as standalone deals.
2. Add ads in that order while the bundle still has a score of 1.0 or less.
   An ad that would push the bundle over 1.0 stays out.

Each seller then gives at most one deal: the bundle, or their best single ad
if nothing combines. Leave subset searches and cross-seller logic out.

## Steps

### 1. Script: `scout/deals.py candidates`

- Compute the price, budget and score for every ad that matched films.
- Do the bundling using a **loose ceiling** (score of 2.0 or less), so that
  calibration later has room.
- Write `scout/nl/deals-candidates.txt`. Each line is:

  `id | seller | title | full description | films: slug = Title [tag] (bd|4k) | price, type, delivery, place`

  Expect somewhere from 100 to 250 lines. If there are far more, tighten the
  ceiling before going on.

### 2. Sonnet check

Split the shortlist in two (`split -n l/2`) and run one Sonnet agent on each,
with Read and Write only. Don't use Haiku here, because it lets doubtful ads
through. The rules and the output format are in `scout/deals-check-brief.md`:
drop region A-only, badly damaged, disc-missing, sold, wanted and DVD-only
ads, correct each film's format and its real price, and flag `wear`,
`region?`, `multibuy`, `steelbook` and `sealed`. The agents write
`nl/deals-check-<n>.jsonl`. Later files override earlier ones, so a fix for
a few ads can go in a file of its own.

### 3. Script: `scout/deals.py pick`

- Apply the drops and the format corrections, then redo the scores and
  bundles.
- Calibrate against the target of **about 30 deals**. Anything from 25 to 35
  is fine.
  1. Count the deals that hold at least one 4K film at €12. If fewer than
     about 5, raise the 4K threshold in steps of €2 (up to €20) until about 5
     to 8 show up.
  2. Move the Blu-ray threshold in steps of €0.50 until the total lands in the
     target. Start at €4. Going up to €6 is fine, and going down is fine too
     if there are too many deals.
  3. Record the final thresholds. The page states them.
- Sort by score. A tie goes to the deal with more films.
- Write `scout/nl/deals.json`.

### 4. Optional live check: up to ~35 requests

The data dates from the 2026-11-13 run. Fetch each final deal's ad page once
to confirm it is still up and the price is the same. Drop or reprice the ad
as needed, and re-run `pick` if the count falls below 25. Skip this step if
the user says requests are tight.

### 5. Render the nationwide page

`nationwide.py render` puts the deals into the **deals** tab of the nationwide
page through `deals.panel()`, one card per seller: the ads with their films
and a BD or 4K chip, the delivered total, the cost per film and the flags.
Republish the nationwide page to its own URL without `capabilities`, so its
stars and trash are kept.

## Don't

- Don't run new Marktplaats searches, and don't refetch beyond step 4.
- Don't edit `scout/films.txt`, `scout/nl/out/` or `results.json`.

## Rough cost

| step | cost |
|---|---|
| the Sonnet check, about 440 ads in two agents | about 240k tokens |
| the scripts | negligible |
| the live check | about 35 requests |
