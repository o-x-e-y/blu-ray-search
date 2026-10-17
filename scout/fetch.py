#!/usr/bin/env python3
"""Write listings.json: every Blu-ray listed in the last day around the user's routes.

Runs the same three searches as the user's Marktplaats saved searches, without
logging in. Reserved listings are left out.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
API = "https://www.marktplaats.nl/lrp/api/search"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
SEARCHES = [("5611AC", 8000), ("5701RJ", 8000), ("5735SZ", 6000)]  # Eindhoven, Helmond, home
# A day plus slack for a late scheduler start; repeats are dropped by id here and
# carried over by id in render.py.
WINDOW_HOURS = 26
PAGE = 100


def search(postcode: str, distance: int, since_ms: int) -> list[dict]:
    listings, offset = [], 0
    while True:
        query = urllib.parse.urlencode({
            "l1CategoryId": 1744, "l2CategoryIds": 1745, "postcode": postcode, "distanceMeters": distance,
            "attributesByKey[]": f"offeredSince:{since_ms}", "limit": PAGE, "offset": offset,
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
    since_ms = int((time.time() - WINDOW_HOURS * 3600) * 1000)
    seen = {}
    for postcode, distance in SEARCHES:
        try:
            found = search(postcode, distance, since_ms)
        except OSError as e:
            sys.exit(f"search around {postcode} failed: {e}")
        print(f"{postcode} +{distance // 1000} km: {len(found)}", file=sys.stderr)
        for l in found:
            if l["itemId"] in seen or l.get("reserved"):
                continue
            seen[l["itemId"]] = {
                "id": l["itemId"],
                "title": l["title"],
                "description": l.get("description", ""),
                "price": price(l["priceInfo"]),
                "town": l["location"].get("cityName", ""),
                "url": "https://www.marktplaats.nl" + l["vipUrl"],
                "seller": l["sellerInformation"].get("sellerName", ""),
            }
    (HERE / "listings.json").write_text(json.dumps(list(seen.values()), ensure_ascii=False, indent=1))
    print(f"listings.json: {len(seen)} unique listings")


if __name__ == "__main__":
    main()
