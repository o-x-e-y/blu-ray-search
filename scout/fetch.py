#!/usr/bin/env python3
"""Write listings.json: every Blu-ray listed around the user's routes since the last run.

    fetch.py [previous.html]

Runs the same three searches as the user's Marktplaats saved searches, without
logging in. previous.html is the currently published page: its fetch time is
where this run starts, and listings it already tracks are left out, as are
reserved ones. Without it, the search covers the last 26 hours.
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
WINDOW_HOURS = 26
# In case a listing reaches the search a little after its posting time.
MARGIN_MS = 3600 * 1000
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
    started = int(time.time() * 1000)
    previous = {}
    if len(sys.argv) > 1:
        found = DATA.search(Path(sys.argv[1]).read_text())
        if found:
            previous = json.loads(found.group(1))
    since_ms = (previous["fetched_at"] - MARGIN_MS if "fetched_at" in previous
                else started - WINDOW_HOURS * 3600 * 1000)
    print(f"listed since {time.strftime('%Y-%m-%d %H:%M %Z', time.localtime(since_ms / 1000))}", file=sys.stderr)
    tracked = {i["id"] for i in previous.get("items", [])}
    seen = {}
    for postcode, distance in SEARCHES:
        try:
            found = search(postcode, distance, since_ms)
        except OSError as e:
            sys.exit(f"search around {postcode} failed: {e}")
        print(f"{postcode} +{distance // 1000} km: {len(found)}", file=sys.stderr)
        for l in found:
            if l["itemId"] in seen or l["itemId"] in tracked or l.get("reserved"):
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
    listings = list(seen.values())
    (HERE / "listings.json").write_text(json.dumps({"fetched_at": started, "listings": listings},
                                                   ensure_ascii=False, indent=1))
    print(f"listings.json: {len(listings)} unique listings")


if __name__ == "__main__":
    main()
