#!/usr/bin/env python3
"""Blu-ray Scout over all of Marktplaats, as a separate page.

    nationwide.py fetch           every Blu-ray listing -> nl/raw.json, then build
    nationwide.py build           nl/raw.json -> nl/listings.json, nl/chunk-*.txt
    (agents match each chunk into nl/out/chunk-*.jsonl, following nationwide-brief.md)
    nationwide.py merge           nl/out/*.jsonl -> nl/results.json, nl/needs_full.json
    nationwide.py full            the cut-off sets in nl/needs_full.json -> nl/full.txt
    (an agent matches nl/full.txt into nl/out/full.jsonl, then merge again)
    nationwide.py render          nl/results.json -> nl/page.html

The search caps a query at 50 pages of 100, so fetch splits the country into
radius searches small enough to page through. A price filter would split it
more cheaply, but every price filter drops about 7% of ads. Search results
carry coordinates, the seller and the delivery options, so only the cut-off
sets' own pages are opened.
"""
import html
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import render
from fetch import API, UA, posted, price

HERE = Path(__file__).parent
OUT = HERE / "nl"
HOME_AT = (51.510, 5.637)  # 5735SZ, Aarle-Rixtel
# Postcodes and radii (km) covering the country, smaller where ads are dense.
CIRCLES = [
    ("9711", 30), ("9671", 25), ("9501", 25), ("9401", 25), ("7811", 30), ("8911", 30), ("8601", 25),
    ("8861", 20), ("9201", 25), ("8441", 25), ("7901", 25), ("8301", 25), ("8011", 25), ("8261", 15),
    ("8232", 25), ("7511", 25), ("7411", 20), ("7311", 25), ("7001", 25), ("7101", 20), ("6811", 20),
    ("6511", 15), ("6711", 20), ("3841", 20), ("3811", 20), ("1781", 25), ("1811", 15), ("1621", 20),
    ("1441", 10), ("1012", 12), ("1315", 15), ("1211", 15), ("2011", 12), ("2201", 10), ("2311", 10),
    ("2405", 10), ("2511", 8), ("2671", 8), ("2611", 8), ("2711", 8), ("2801", 10), ("3011", 6),
    ("3072", 6), ("3051", 6), ("3121", 5), ("2901", 8), ("3201", 10), ("3221", 12), ("3311", 10),
    ("4201", 15), ("3511", 15), ("4001", 15), ("4331", 25), ("4461", 20), ("4301", 20), ("4531", 25),
    ("4611", 15), ("4701", 15), ("4811", 15), ("5038", 15), ("5211", 12), ("5341", 12), ("5401", 15),
    ("5611", 15), ("5701", 15), ("5735", 10), ("5911", 20), ("6001", 20), ("6041", 20), ("6211", 20),
    ("6411", 15),
    # Gaps the first run showed, found through the price searches.
    ("5575", 10), ("7461", 12), ("7671", 10), ("7681", 10), ("4101", 10), ("4153", 8), ("1941", 8),
    ("1521", 6), ("3641", 10), ("3441", 8), ("2861", 8), ("2151", 8), ("1181", 6), ("3284", 12),
    ("5241", 8), ("5527", 8), ("6127", 10), ("5161", 8), ("5111", 10), ("5763", 8), ("5854", 10),
]
RUN = date.today()  # once, so a fetch running past midnight keeps one cache
CONDITIONS = [13366, 13367, 13368]  # nieuw in verpakking, zo goed als nieuw, gebruikt
# A radius search leaves out ads listed without a location, from webshops
# (CARDUELIS & MEDIA, Lamar Games, ~3,750 ads in all), and Belgian ones. A price filter
# drops ~7% of ads, so it can't replace the circles, but it does include those.
# The shop's most common prices get searched on their own, since they're too
# dense to share a range; everything between them goes in ranges.
SHOP_PRICES = [350, 500, 750, 1000, 1200, 1500, 2000, 2250, 2500, 2750, 2950, 3000, 3250, 6500]
NEAR_KM = 30
CAP = 5000
CHUNK = 1000


def page(key: str, params: list, offset: int) -> dict:
    """One page of a search, cached under key so an interrupted fetch picks up where it stopped."""
    cached = OUT / f"pages-{RUN}" / f"{key}-{offset}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    params = [("l1CategoryId", 1744), ("l2CategoryIds", 1745), ("limit", 100), ("offset", offset), *params]
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            time.sleep(1)
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(body)
            return json.loads(body)
        except OSError as e:
            print(f"  {key} @{offset}: {e}, retrying", file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    sys.exit(f"{key} failed three times; rerun to resume from the cache")


def collect(key: str, params: list, total: int, first: dict, found: dict) -> None:
    result, offset = first, 0
    while result["listings"]:
        found |= {l["itemId"]: l for l in result["listings"]}
        offset += 100
        if offset >= min(total, CAP):
            break
        result = page(key, params, offset)


def circle(postcode: str, km: int, found: dict) -> None:
    radius = lambda km: [("postcode", postcode), ("distanceMeters", km * 1000)]
    first = page(f"{postcode}-{km}", radius(km), 0)
    total = first["totalResultCount"]
    while total > CAP:
        smaller = int(km * 0.7)
        print(f"  {postcode} {km} km: {total} is over the cap; {smaller}-{km} km has to come from neighbours",
              file=sys.stderr)
        km = smaller
        first = page(f"{postcode}-{km}", radius(km), 0)
        total = first["totalResultCount"]
    collect(f"{postcode}-{km}", radius(km), total, first, found)
    print(f"{postcode} {km} km: {total}, {len(found)} so far", file=sys.stderr, flush=True)


def prices(low: int, high: int, found: dict) -> None:
    """Every ad priced low..high cents, nationwide, which includes ads listed without a location.

    Unsorted: a sorted search leaves those ads out. A range over the cap is
    halved; a single price over it is split by condition, losing only the
    over-cap ads that state none.
    """
    before = len(found)
    key, price = f"price{low}-{high}", [("attributeRanges[]", f"PriceCents:{low}:{high}")]
    if low == high:
        key = f"price{low}"
    first = page(key, price, 0)
    total = first["totalResultCount"]
    if total <= CAP:
        collect(key, price, total, first, found)
    elif low < high:
        mid = (low + high) // 2
        prices(low, mid, found)
        prices(mid + 1, high, found)
        return
    else:
        split = 0
        for condition in CONDITIONS:
            params = price + [("attributesById[]", condition)]
            first = page(f"{key}-c{condition}", params, 0)
            split += first["totalResultCount"]
            collect(f"{key}-c{condition}", params, first["totalResultCount"], first, found)
        print(f"  €{low / 100:g}: {total - split} ads state no condition and may be missed", file=sys.stderr)
    print(f"€{low / 100:g}-{high / 100:g}: {total}, {len(found) - before} new, {len(found)} so far",
          file=sys.stderr, flush=True)


def km_from_home(location: dict) -> int:
    lat1, lon1, lat2, lon2 = map(math.radians, (*HOME_AT, location.get("latitude", 0), location.get("longitude", 0)))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return round(12742 * math.asin(math.sqrt(a)))


def clean(text: str) -> str:
    """Rejoin surrogate pairs and turn lone ones, which some ads contain, into U+FFFD."""
    return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def entry(l: dict, today: date) -> dict:
    seller = l["sellerInformation"]
    slug = re.sub(r"[^a-z0-9]+", "-", seller.get("sellerName", "").lower()).strip("-") or "x"
    delivery = next((a["value"] for a in l.get("attributes", []) if a["key"] == "delivery"), "")
    return {
        "id": l["itemId"],
        "title": clean(l["title"]),
        "description": clean(l.get("categorySpecificDescription") or l.get("description", "")).removesuffix("..."),
        "price": price(l["priceInfo"]),
        "town": clean(l["location"].get("cityName", "")),
        "km": km_from_home(l["location"]) if l["location"].get("latitude") else None,
        "delivery": delivery,
        "url": "https://www.marktplaats.nl" + l["vipUrl"],
        "seller": {"id": seller["sellerId"], "name": clean(seller.get("sellerName", "")),
                   "url": f"https://www.marktplaats.nl/u/{slug}/{seller['sellerId']}/"},
        "since": posted(l.get("date", ""), today),
        "reserved": bool(l.get("reserved")),
    }


def fetch() -> None:
    OUT.mkdir(exist_ok=True)
    total = page("-0", [], 0)["totalResultCount"]
    found = {}
    for postcode, km in CIRCLES:
        circle(postcode, km, found)
    for cents in SHOP_PRICES:
        prices(cents, cents, found)
    for low, high in zip([0] + [c + 1 for c in SHOP_PRICES], [c - 1 for c in SHOP_PRICES] + [100_000_000]):
        prices(low, high, found)
    (OUT / "raw.json").write_text(json.dumps({"date": str(RUN), "total": total, "listings": found}))
    build()


def build() -> None:
    """Turn nl/raw.json into listings.json and the chunks, so a failure here costs no requests."""
    raw = json.loads((OUT / "raw.json").read_text())
    total, found = raw["total"], raw["listings"]
    today = date.fromisoformat(raw["date"])
    listings = [entry(l, today) for l in found.values()]
    reserved = sum(l["reserved"] for l in listings)
    listings = [l for l in listings if not l["reserved"]]
    undated = sum(not l["since"] for l in listings)
    (OUT / "listings.json").write_text(json.dumps(listings, ensure_ascii=False, indent=1))
    for old in OUT.glob("chunk-*.txt"):
        old.unlink()
    for n in range(0, len(listings), CHUNK):
        lines = [f'{l["id"]} | {" ".join(l["title"].split())} | {" ".join(l["description"].split())}'
                 for l in listings[n:n + CHUNK]]
        (OUT / f"chunk-{n // CHUNK:02d}.txt").write_text("\n".join(lines) + "\n")
    print(f"{len(found)} of {total} listed fetched, {reserved} reserved left out, "
          f"{len(listings)} written in {-(-len(listings) // CHUNK)} chunks, {undated} without a parsed date")


def merge() -> None:
    """Check the agents' lines against the chunks and films.txt, and combine them."""
    films = set(render.films_by_slug())
    items, needs_full, problems = {}, [], []

    def tidy(o: dict) -> dict:
        bad = [s for s in o.get("films", []) if s not in films]
        if bad:
            problems.append(f"{o['id']}: unknown slugs {bad}")
        o["films"] = [s for s in o.get("films", []) if s in films]
        o["flags"], o["note"] = list(o.get("flags") or []), o.get("note") or ""
        if not isinstance(o.get("films_in_listing"), int):
            if isinstance(o.get("films_in_listing"), list):  # a flag put in the wrong field
                o["flags"] += [f for f in o["films_in_listing"] if isinstance(f, str)]
            o["films_in_listing"] = max(1, len(o["films"]))
        return o

    for chunk in sorted(OUT.glob("chunk-*.txt")):
        out = OUT / "out" / f"{chunk.stem}.jsonl"
        if not out.exists():
            problems.append(f"{out.name} missing")
            continue
        ids = {line.split(" | ")[0] for line in chunk.read_text().splitlines()}
        for line in filter(str.strip, out.read_text().splitlines()):
            o = json.loads(line)
            if o.get("id") not in ids:
                problems.append(f"{out.name}: {o.get('id')} isn't in its chunk")
                continue
            if o.pop("needs_full", False):
                needs_full.append(o["id"])
            items[o["id"]] = tidy(o)
    full = OUT / "out" / "full.jsonl"
    if full.exists():
        for line in filter(str.strip, full.read_text().splitlines()):
            o = tidy(json.loads(line))
            if not o["films"] and not o.get("unknown_contents"):
                items.pop(o["id"], None)
            else:
                items[o["id"]] = o
    print("\n".join(problems) or "no problems", file=sys.stderr)
    listings = json.loads((OUT / "listings.json").read_text())
    (OUT / "results.json").write_text(json.dumps({"date": json.loads((OUT / "raw.json").read_text())["date"],
                                                  "listings_seen": len(listings), "items": list(items.values())},
                                                 ensure_ascii=False, indent=1))
    (OUT / "needs_full.json").write_text(json.dumps(needs_full))
    print(f"results.json: {len(items)} finds, {len(needs_full)} cut-off sets")


def full() -> None:
    """Fetch the whole description of each cut-off set in nl/needs_full.json into nl/full.txt."""
    listings = {l["id"]: l for l in json.loads((OUT / "listings.json").read_text())}
    cache = OUT / "full"
    cache.mkdir(exist_ok=True)
    lines = []
    for n, id_ in enumerate(json.loads((OUT / "needs_full.json").read_text())):
        cached = cache / f"{id_}.html"
        if not cached.exists():
            url = listings[id_]["url"].split("?")[0]
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r:
                    cached.write_bytes(r.read())
            except OSError as e:
                print(f"  {id_}: {e}", file=sys.stderr)
                continue
            finally:
                time.sleep(1)
        found = re.search(r'data-collapsable="description">(.*?)</div>', cached.read_text(errors="replace"), re.S)
        text = html.unescape(re.sub(r"<[^>]+>", " ", found.group(1))) if found else listings[id_]["description"]
        lines.append(f'{id_} | {" ".join(listings[id_]["title"].split())} | {" ".join(clean(text).split())}')
        if n % 25 == 0:
            print(f"{n} pages", file=sys.stderr, flush=True)
    (OUT / "full.txt").write_text("\n".join(lines) + "\n")
    print(f"full.txt: {len(lines)} ads")


def far(item: dict) -> int:
    """Distance for sorting; ads without a location (webshops, Belgium) go last."""
    return 10_000 if item["km"] is None else item["km"]


def card(item: dict, films: dict, today: str, chips: bool, kind: bool = False) -> str:
    out = render.card(item, films, today, chips, kind)
    if far(item) <= NEAR_KM:
        out = out.replace('" target="_blank" rel="noopener">', f'" target="_blank" rel="noopener"><span class="badge near">≤{NEAR_KM} km</span>', 1)
    where = html.escape(item["town"] or "no location given") + ("" if item["km"] is None else f' · {item["km"]} km')
    return out.replace('<div class="where">' + html.escape(item["town"]), '<div class="where">' + where, 1)


def by_film(items: list, films: dict, today: str) -> tuple[str, int]:
    groups = {}
    for item in items:
        groups.setdefault(item["films"][0], []).append(item)
    rank = lambda slug: (-render.stars(films[slug]["tag"]), films[slug]["title"])
    order = lambda i: (far(i) > NEAR_KM, "pickup only" in i["flags"], far(i))
    out = []
    for slug in sorted(groups, key=rank):
        cards = "".join(card(i, films, today, chips=False) for i in sorted(groups[slug], key=order))
        out.append(f'<div class="film"><h3>{render.film_link(slug, films[slug]["title"])} '
                   f'{render.tag_html(films[slug]["tag"])}</h3>{cards}</div>')
    return "".join(out), len(groups)


def render_page() -> None:
    results = json.loads((OUT / "results.json").read_text())
    listings = {l["id"]: l for l in json.loads((OUT / "listings.json").read_text())}
    full_text = {}
    for line in (OUT / "full.txt").read_text().splitlines():
        id_, _, desc = (line.split(" | ", 2) + ["", ""])[:3]
        full_text[id_] = desc
    films = render.films_by_slug()
    today = results["date"]
    items = []
    for match in results["items"]:
        item = listings[match["id"]] | match
        item["description"] = full_text.get(match["id"], item["description"])
        item["films"] = list(dict.fromkeys(s for s in match["films"] if s in films))
        if match["films"] and not item["films"]:
            continue
        item["found"] = today
        item["detour"] = False
        item["flags"] = list(item.get("flags", []))
        if item["delivery"] == "Ophalen" and far(item) > NEAR_KM:
            item["flags"].append("pickup only")
        items.append(item)

    best = lambda i: max(render.stars(films[s]["tag"]) for s in i["films"]) if i["films"] else -1
    matched = [i for i in items if i["films"]]
    sets = sorted((i for i in matched if (i.get("films_in_listing") or 1) >= 2),
                  key=lambda i: (-best(i), -len(i["films"]), far(i)))
    singles = [i for i in matched if i not in sets]
    watchlisted = lambda i: any(films[s]["tag"] == "watchlist" for s in i["films"])
    seen, seen_n = by_film([i for i in singles if best(i) > 0], films, today)
    wanted, wanted_n = by_film([i for i in singles if best(i) == 0 and watchlisted(i)], films, today)
    extra, extra_n = by_film([i for i in singles if best(i) == 0 and not watchlisted(i)], films, today)
    lots = sorted((i for i in items if not i["films"]), key=far)

    sections = "".join([
        render.section("Seen", seen, seen_n, "Films you rated 4★ or higher, best-rated first. Within a film, ads near home first."),
        render.section("Watchlisted", wanted, wanted_n, "Films on your watchlist."),
        render.section("Also wanted", extra, extra_n, "Films from wanted.txt, wanted for another reason."),
        render.section("Sets", "".join(card(i, films, today, chips=True) for i in sets), len(sets)),
        render.section("Collections to look into", "".join(card(i, films, today, chips=False) for i in lots), len(lots),
                       "Big lots whose ads don't list every title."),
    ])
    groups = {}
    for item in sets + singles + lots:
        groups.setdefault(item["seller"]["id"], []).append(item)
    out = []
    for group in sorted(groups.values(), key=lambda g: (-max(map(best, g)), -len(g))):
        group.sort(key=best, reverse=True)
        seller = group[0]["seller"]
        towns = ", ".join(dict.fromkeys(i["town"] for i in group))
        count = f' <small>[{len(group)} ads]</small>' if len(group) > 1 else ""
        cards = "".join(card(i, films, today, chips=True, kind=True) for i in group)
        out.append(f'<div class="film seller"><h3><a href="{html.escape(seller["url"])}" target="_blank" rel="noopener">'
                   f'{html.escape(seller["name"])}</a>{count} <span class="town">{html.escape(towns)}</span></h3>{cards}</div>')
    by_seller = render.section("By seller", "".join(out), len(groups),
                               "Grouped by who sells it, so one message or one shipment can cover several ads. Best-rated film first, then sellers with the most ads.")
    near = sum(far(i) <= NEAR_KM for i in items)
    stats = (f'<span>listings read <b>{results["listings_seen"]}</b></span><span>matched <b>{len(items)}</b></span>'
             f'<span>within {NEAR_KM} km <b>{near}</b></span><span>sellers <b>{len(groups)}</b></span>')
    lede = (f"Every Blu-ray listed on Marktplaats, matched against your Letterboxd films rated 4★ or higher, your "
            f"watchlist and the films you want for someone else. Ads within {NEAR_KM} km of home are marked; far ads that can only be picked up are flagged. "
            f"Reserved listings are left out. Listings fetched {today}.")
    page_ = (HERE / "template.html").read_text()
    page_ = page_.replace("<title>Blu-ray Scout</title>", "<title>Blu-ray Scout NL</title>")
    page_ = re.sub(r'<p class="lede">.*?</p>', f'<p class="lede">{html.escape(lede)}</p>', page_, count=1, flags=re.S)
    page_ = re.sub(r'\s*<a class="rerun".*?</a>', "", page_, count=1, flags=re.S)
    page_ = re.sub(r'\s*<button role="tab"[^>]*aria-controls="players".*?</button>', "", page_, count=1, flags=re.S)
    page_ = re.sub(r'\s*<div class="panel"[^>]*id="players".*?</div>', "", page_, count=1, flags=re.S)
    page_ = page_.replace(".badge.detour {", ".badge.near { background: var(--ok); color: var(--bg); padding: 0 6px; }\n"
                                             ".badge.near::before, .badge.near::after { content: none; }\n.badge.detour {")
    data = json.dumps({"films": sorted(films), "items": items}, ensure_ascii=False).replace("</", "<\\/")
    for key, value in {"__STATS__": stats, "__BY_FILM__": sections, "__BY_SELLER__": by_seller, "__DATA__": data}.items():
        page_ = page_.replace(key, value)
    (OUT / "page.html").write_text(page_)
    print(f"page.html: {len(items)} finds, {len(sets)} sets, {seen_n} seen and {wanted_n} watchlisted films, "
          f"{extra_n} also wanted, {len(lots)} lots, {near} within {NEAR_KM} km")


if __name__ == "__main__":
    {"fetch": fetch, "build": build, "merge": merge, "full": full, "render": render_page}[sys.argv[1]]()
