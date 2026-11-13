"""Cheapest ways to get listed films off the nationwide data: see deals-brief.md.

candidates: shortlist ads whose seller bundle could qualify, for the Sonnet check.
pick: apply the check, calibrate thresholds to about 30 deals, write nl/deals.json.
panel(): the deals tab of the nationwide page, from nl/deals.json.
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
NL = HERE / "nl"
SHIPPING = 3.0
FREE_PICKUP = {"eindhoven", "helmond", "mierlo", "stiphout"}
NEAR_KM = 30
DROP_FLAGS = {"DVD", "damaged", "region 1", "region C"}
FOURK = re.compile(r"\b(4k|uhd|ultra ?hd)\b", re.I)
EUROS = re.compile(r"(?:€|eur[o]?)\s*(\d+(?:[.,]\d{1,2})?)|(\d+(?:[.,]\d{1,2})?)\s*(?:€|euro|eur)\b", re.I)


def ad_text() -> dict:
    text = {}
    for f in sorted(NL.glob("chunk-*.txt")) + [NL / "full.txt"]:
        for line in f.read_text().splitlines():
            id_, title, desc = (line.split(" | ", 2) + ["", ""])[:3]
            text[id_] = (title, " ".join(desc.split()))
    return text


def films_by_slug() -> dict:
    out = {}
    for line in (HERE / "films.txt").read_text().splitlines():
        slug, title, tag = [p.strip() for p in line.split("|")]
        out[slug] = {"title": title, "tag": tag}
    return out


def parse_price(price: str, desc: str) -> tuple[float | None, list]:
    """Asking price in euros and how it was read; None when there is none to go on."""
    amount = lambda s: float(s.replace(",", "."))
    if m := re.fullmatch(r"€([\d,]+)", price):
        return amount(m[1]), []
    if m := re.fullmatch(r"bieden vanaf €([\d,]+)", price):
        return amount(m[1]), ["bid"]
    if price == "gratis":
        return 0.0, []
    found = [amount(a or b) for a, b in EUROS.findall(desc)]
    found = [f for f in found if f > 0]
    return (min(found), ["price from text"]) if found else (None, [])


def load() -> list:
    results = json.loads((NL / "results.json").read_text())["items"]
    listings = {l["id"]: l for l in json.loads((NL / "listings.json").read_text())}
    text, films = ad_text(), films_by_slug()
    ads = []
    for match in results:
        l = listings[match["id"]]
        slugs = [s for s in dict.fromkeys(match["films"]) if s in films]
        if not slugs or l["reserved"] or DROP_FLAGS & set(match["flags"]):
            continue
        far = l["km"] is None or l["km"] > NEAR_KM
        town = l["town"].lower()
        if l["delivery"] == "Ophalen" and far and town not in FREE_PICKUP:
            continue
        title, desc = text.get(match["id"], (l["title"], l["description"]))
        cost, flags = parse_price(l["price"], desc)
        if cost is None:
            continue
        fourk = "4K only" in match["flags"] or bool(FOURK.search(title + " " + desc))
        fmt = "4k" if fourk and len(slugs) == 1 else "bd"
        if fourk and len(slugs) > 1:
            flags.append("4k?")
        if "region A" in match["flags"]:
            flags.append("region A")
        if "3D only" in match["flags"]:
            flags.append("3D")
        if town in FREE_PICKUP:
            flags.append("pick up free")
        ads.append(l | {"title": title, "description": desc, "films": slugs, "cost": cost, "flags": flags,
                        "format": {s: fmt for s in slugs}, "note": match["note"],
                        "films_in_listing": match["films_in_listing"]})
    return ads


def budget(ad: dict, bd: float, uhd: float) -> float:
    return sum(uhd if f == "4k" else bd for f in ad["format"].values())


def bundles(ads: list, bd: float, uhd: float, ceiling: float) -> list:
    """One deal per seller. Shipping is paid once, so an ad joins when its own price fits its films' budget;
    the bundle qualifies when the total with shipping does."""
    by_seller = {}
    for ad in ads:
        by_seller.setdefault(ad["seller"]["id"], []).append(ad)
    deals = []
    for group in by_seller.values():
        group.sort(key=lambda a: a["cost"] / budget(a, bd, uhd))
        picked, cost, room, seen = [], SHIPPING, 0.0, set()
        for ad in group:
            new = [s for s in ad["films"] if s not in seen]
            extra = sum(uhd if ad["format"][s] == "4k" else bd for s in new)
            if new and ad["cost"] <= extra * ceiling:
                picked.append(ad)
                cost += ad["cost"]
                room += extra
                seen.update(new)
        if picked and cost <= room * ceiling:
            deals.append({"seller": group[0]["seller"], "ads": picked, "cost": round(cost, 2),
                          "films": sorted(seen), "score": round(cost / room, 3)})
    return sorted(deals, key=lambda d: (d["score"], -len(d["films"])))


def excerpt(ad: dict, films: dict, keep: int = 1200) -> str:
    """Long catalogue ads: the opening, then the text around each matched title."""
    desc = ad["description"]
    if len(desc) <= keep:
        return desc
    parts = [desc[:500]]
    for s in ad["films"]:
        name = re.sub(r"\s*\(\d{4}\)$", "", films[s]["title"])
        m = re.search(re.escape(name[:25]), desc, re.I)
        if m:
            parts.append(desc[max(0, m.start() - 80):m.end() + 120])
    return " […] ".join(parts) + " […]"


def candidates() -> None:
    ads = load()
    deals = bundles(ads, 6, 20, 1.0)
    films = films_by_slug()
    lines = []
    for d in deals:
        for ad in d["ads"]:
            matched = "; ".join(f"{s} = {films[s]['title']} ({ad['format'][s]})" for s in ad["films"])
            where = f"{ad['town'] or 'no town'}{'' if ad['km'] is None else f' {ad['km']} km'}"
            lines.append(f"{ad['id']} | {d['seller']['name']} | {ad['title']} | {excerpt(ad, films)} | films: {matched} "
                         f"| {ad['price']} ({', '.join(ad['flags']) or 'no flags'}), {ad['delivery']}, {where} "
                         f"| matcher note: {ad['note'] or '-'}")
    (NL / "deals-candidates.txt").write_text("\n".join(lines) + "\n")
    print(f"{len(ads)} priced ads, {len(deals)} seller deals at the loosest thresholds, {len(lines)} candidate ads")


def pick() -> None:
    checks = {}
    for f in sorted(NL.glob("deals-check-*.jsonl")):
        for line in filter(str.strip, f.read_text().splitlines()):
            o = json.loads(line)
            checks[o["id"]] = o
    ads = []
    for ad in load():
        c = checks.get(ad["id"])
        if c is None or c["drop"]:
            continue
        ad["format"] |= {s: f for s, f in c.get("format", {}).items() if s in ad["format"]}
        if c.get("price") is not None:
            ad["cost"] = float(c["price"])
        ad["films"] = [s for s in ad["films"] if s not in c.get("drop_films", [])]
        ad["format"] = {s: ad["format"][s] for s in ad["films"]}
        if not ad["films"]:
            continue
        ad["flags"] = [f for f in ad["flags"] if f not in ("4k?", "region A", "price from text")] + c.get("flags", [])
        ad["why"] = c.get("why", "")
        ads.append(ad)

    has_4k = lambda deals: sum(any(a["format"][s] == "4k" for a in d["ads"] for s in a["films"]) for d in deals)
    uhd = 12
    while has_4k(bundles(ads, 4, uhd, 1.0)) < 5 and uhd < 20:
        uhd += 2
    bd, deals = 4.0, bundles(ads, 4, uhd, 1.0)
    while len(deals) < 25 and bd < 6:
        bd += 0.5
        deals = bundles(ads, bd, uhd, 1.0)
    while len(deals) > 35 and bd > 2:
        bd -= 0.5
        deals = bundles(ads, bd, uhd, 1.0)
    (NL / "deals.json").write_text(json.dumps({"date": json.loads((NL / "results.json").read_text())["date"],
                                               "bd": bd, "uhd": uhd, "shipping": SHIPPING, "checked": len(checks),
                                               "deals": deals}, ensure_ascii=False, indent=1))
    print(f"BD €{bd:g}, 4K €{uhd:g}: {len(deals)} deals, {has_4k(deals)} with 4K, "
          f"{sum(len(d['films']) for d in deals)} films")


def euros(x: float) -> str:
    return f"€{x:.2f}".replace(".", ",").replace(",00", "")


def panel() -> tuple[str, int]:
    import render as scout
    data = json.loads((NL / "deals.json").read_text())
    films = films_by_slug()
    cards = []
    for d in data["deals"]:
        seller = d["seller"]
        n = len(d["films"])
        ads = []
        for ad in d["ads"]:
            chips = [f'<span class="chip">{scout.film_link(s, films[s]["title"])} {scout.tag_html(films[s]["tag"])}'
                     f' <b>{"4K" if ad["format"][s] == "4k" else "BD"}</b></span>' for s in ad["films"]]
            if (ad.get("films_in_listing") or 1) > len(ad["films"]):
                chips.append(f'<span class="chip dim">{ad["films_in_listing"]} films in ad</span>')
            chips += [f'<span class="chip {"dim" if f in ("pick up free", "sealed", "steelbook", "multibuy") else "flag"}">'
                      f'{html.escape(f)}</span>' for f in ad["flags"]]
            listed = ad["price"]
            price = euros(ad["cost"])
            shown = price if listed == price else f'{price} <small>({html.escape(listed)})</small>'
            where = html.escape(ad["town"] or "no location given") + ("" if ad["km"] is None else f' · {ad["km"]} km')
            why = f'<p class="note">{html.escape(ad["why"])}</p>' if ad.get("why") else ""
            ads.append(f'<div class="item"><div class="row"><a href="{html.escape(ad["url"].split("?")[0])}" target="_blank" '
                       f'rel="noopener">{html.escape(ad["title"])}</a><span class="end"><span class="price">{shown}</span></span></div>'
                       f'<div class="chips">{"".join(chips)}</div><div class="where">{where} · {html.escape(ad["delivery"])}</div>{why}</div>')
        towns = ", ".join(dict.fromkeys(a["town"] for a in d["ads"] if a["town"]))
        head = (f'<a href="{html.escape(seller["url"])}" target="_blank" rel="noopener">{html.escape(seller["name"])}</a> '
                f'<span class="town">{html.escape(towns)}</span>')
        sums = (f'<p class="sum"><b>{euros(d["cost"])}</b> delivered for {n} film{"s" * (n > 1)} · '
                f'<b>{euros(d["cost"] / n)}</b> per film · {round(d["score"] * 100)}% of budget</p>')
        cards.append(f'<div class="film seller"><h3>{head}</h3>{sums}{"".join(ads)}</div>')
    lede = (f"The cheapest ways to get films from your list, from these listings. Costs include {euros(data['shipping'])} "
            f"shipping per seller, so several ads from one seller share it. A deal costs at most {euros(data['bd'])} per Blu-ray "
            f"and {euros(data['uhd'])} per 4K film delivered; discs in a lot that aren't on your list count for nothing. "
            f"Region A-locked, damaged, DVD and sold ads are out, after a check of {data['checked']} shortlisted ads. Best value first.")
    n = len(data["deals"])
    return (f'<section><h2>Deals <small>[{n}]</small></h2><p class="note">{html.escape(lede)}</p>'
            f'<div class="list">{"".join(cards)}</div></section>'), n


if __name__ == "__main__":
    {"candidates": candidates, "pick": pick}[sys.argv[1]]()
