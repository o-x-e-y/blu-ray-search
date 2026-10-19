#!/usr/bin/env python3
"""Write listings.json: what's listed around the user's routes, and which of it is new.

    fetch.py [previous.html]

Runs the same three searches as the user's Marktplaats saved searches, without
logging in, over everything currently listed. previous.html is the currently
published page. It stores the ids the last published run saw, and a listing
not among them is new. Without it, listings posted today or yesterday count as
new. Listings the page already tracks and reserved ones are never new.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from render import DATA

HERE = Path(__file__).parent
API = "https://www.marktplaats.nl/lrp/api/search"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
SEARCHES = [("5611AC", 8000), ("5701RJ", 8000), ("5735SZ", 6000)]  # Eindhoven, Helmond, home
PAGE = 100


def search(postcode: str, distance: int) -> list[dict]:
    listings, offset = [], 0
    while True:
        query = urllib.parse.urlencode({
            "l1CategoryId": 1744, "l2CategoryIds": 1745, "postcode": postcode, "distanceMeters": distance,
            "limit": PAGE, "offset": offset,
        })
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
            found = search(postcode, distance)
        except OSError as e:
            sys.exit(f"search around {postcode} failed: {e}")
        print(f"{postcode} +{distance // 1000} km: {len(found)}", file=sys.stderr)
        area |= {l["itemId"]: l for l in found}
    if "seen" in previous:
        seen = set(previous["seen"])
        new = lambda l: l["itemId"] not in seen
    else:
        new = lambda l: l["date"] in ("Vandaag", "Gisteren")
    listings = [{
        "id": l["itemId"],
        "title": l["title"],
        "description": l.get("description", ""),
        "price": price(l["priceInfo"]),
        "town": l["location"].get("cityName", ""),
        "url": "https://www.marktplaats.nl" + l["vipUrl"],
        "seller": l["sellerInformation"].get("sellerName", ""),
    } for l in area.values() if new(l) and l["itemId"] not in tracked and not l.get("reserved")]
    (HERE / "listings.json").write_text(json.dumps({
        "seen": sorted(area),
        "reserved": sorted(i for i, l in area.items() if l.get("reserved")),
        "listings": listings,
    }, ensure_ascii=False, indent=1))
    print(f"listings.json: {len(area)} listed in the area, {len(listings)} new")


if __name__ == "__main__":
    main()
