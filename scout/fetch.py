#!/usr/bin/env python3
"""Write listings.json: what's listed around the user's routes, and which of it is new.

    fetch.py [previous.html]

Runs the same three searches as the user's Marktplaats saved searches, without
logging in, over everything currently listed. previous.html is the currently
published page. It stores the ids the last published run saw, and a listing
not among them is new. Without it, listings posted today or yesterday count as
new. Listings the page already tracks and reserved ones are never new.

The page also stores the film list it was matched against. Films added to
films.txt since then go in recheck, with every listing that isn't new, so ads
seen before get matched against them too.

It also searches the whole country for 4K Blu-ray players and keeps the ones
whose title or description names a 4K model. "4K upscaling" players can't play
4K discs, so the pattern looks for model names rather than "4K".
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from render import DATA, films_by_slug

HERE = Path(__file__).parent
API = "https://www.marktplaats.nl/lrp/api/search"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
SEARCHES = [("5611AC", 8000), ("5701RJ", 8000), ("5735SZ", 6000)]  # Eindhoven, Helmond, home
PAGE = 100
DISCS = {"l1CategoryId": 1744, "l2CategoryIds": 1745}
PLAYERS = {"l1CategoryId": 31, "l2CategoryIds": 2665}
PLAYER_QUERIES = ["4k", "uhd"]
MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
UHD = re.compile(r"\b(?:dp|dmp|dmr)[- ]?ub|\bubp[- ]?x\d|\bubk\d|\bubd[- ]?[km]?\d|\budp[- ]?(?:lx)?\d|\bubr[- ]?x\d|\bup970\b"
                 r"|\bbdp[- ]?750\d|ultra[- ]?hd blu|uhd blu|4k uhd (?:blu|speler|player)", re.I)


def posted(text: str, today: date) -> str:
    if text == "Vandaag":
        return today.isoformat()
    if text in ("Gisteren", "Eergisteren"):
        return (today - timedelta(days=1 if text == "Gisteren" else 2)).isoformat()
    m = re.fullmatch(r"(\d{1,2}) (\w{3})\.?(?: '?(\d{2}))?", text)
    if not m or m.group(2) not in MONTHS:
        return ""
    day, month = int(m.group(1)), MONTHS.index(m.group(2)) + 1
    year = 2000 + int(m.group(3)) if m.group(3) else today.year
    d = date(year, month, day)
    return (d.replace(year=year - 1) if d > today else d).isoformat()


def search(params: dict) -> list[dict]:
    listings, offset = [], 0
    while True:
        query = urllib.parse.urlencode({**params, "limit": PAGE, "offset": offset})
        with urllib.request.urlopen(urllib.request.Request(f"{API}?{query}", headers={"User-Agent": UA}),
                                    timeout=30) as r:
            page = json.load(r)
        listings += page["listings"]
        offset += PAGE
        time.sleep(1)
        if offset >= page.get("totalResultCount", 0) or not page["listings"]:
            return listings


def price(info: dict) -> str:
    euros = f"€{info.get('priceCents', 0) / 100:.2f}".replace(".", ",").replace(",00", "")
    return {"FIXED": euros, "MIN_BID": f"bieden vanaf {euros}" if info.get("priceCents") else "bieden",
            "FAST_BID": "bieden", "SEE_DESCRIPTION": "zie omschrijving", "FREE": "gratis",
            "NOTK": "n.o.t.k.", "EXCHANGE": "ruilen"}.get(info["priceType"], info["priceType"].lower())


def entry(l: dict) -> dict:
    return {
        "id": l["itemId"],
        "title": l["title"],
        "description": l.get("description", ""),
        "price": price(l["priceInfo"]),
        "town": l["location"].get("cityName", ""),
        "url": "https://www.marktplaats.nl" + l["vipUrl"],
        "seller": l["sellerInformation"].get("sellerName", ""),
    }


def players() -> list[dict]:
    found = {}
    for q in PLAYER_QUERIES:
        found |= {l["itemId"]: l for l in search({**PLAYERS, "query": q})}
    return [entry(l) | {"delivery": next((a["value"] for a in l.get("attributes", []) if a["key"] == "delivery"), ""),
                        "since": posted(l.get("date", ""), date.today())}
            for l in found.values()
            if UHD.search(f'{l["title"]} {l.get("description", "")}') and not l.get("reserved")
            and not l["title"].lower().startswith("gezocht")]


def main() -> None:
    previous = {}
    if len(sys.argv) > 1:
        found = DATA.search(Path(sys.argv[1]).read_text())
        if found:
            previous = json.loads(found.group(1))
    tracked = {i["id"] for i in previous.get("items", [])}
    area = {}
    for postcode, distance in SEARCHES:
        try:
            found = search({**DISCS, "postcode": postcode, "distanceMeters": distance})
        except OSError as e:
            sys.exit(f"search around {postcode} failed: {e}")
        print(f"{postcode} +{distance // 1000} km: {len(found)}", file=sys.stderr)
        area |= {l["itemId"]: l for l in found}
    try:
        found_players = players()
    except OSError as e:
        sys.exit(f"4K player search failed: {e}")
    if "seen" in previous:
        seen = set(previous["seen"])
        new = lambda l: l["itemId"] not in seen
    else:
        new = lambda l: l["date"] in ("Vandaag", "Gisteren")
    untracked = [l for l in area.values() if l["itemId"] not in tracked and not l.get("reserved")]
    listings = [entry(l) for l in untracked if new(l)]
    # A page from before the film list was stored gets everything rechecked once.
    added = sorted(set(films_by_slug()) - set(previous.get("films", [])))
    recheck = [entry(l) for l in untracked if not new(l)] if added else []
    (HERE / "listings.json").write_text(json.dumps({
        "seen": sorted(area),
        "reserved": sorted(i for i, l in area.items() if l.get("reserved")),
        "listings": listings,
        "recheck": {"films": added, "listings": recheck},
        "players": found_players,
    }, ensure_ascii=False, indent=1))
    print(f"listings.json: {len(area)} listed in the area, {len(listings)} new, "
          f"{len(recheck)} to recheck against {len(added)} added films, "
          f"{len(found_players)} 4K players")


if __name__ == "__main__":
    main()
