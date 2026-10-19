#!/usr/bin/env python3
"""Check every tracked listing and render page.html.

    render.py results.json [previous.html] [--no-check]

previous.html is the currently published page. Its finds are carried over
(deduplicated by listing id) for as long as the listing is still up. Each
listing's own page says whether it is available, reserved or gone, and since
when it has been online. Only available finds are shown. Reserved ones stay
tracked in case the reservation falls through; gone ones are dropped.
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path

HERE = Path(__file__).parent
DATA = re.compile(r'<script type="application/json" id="scout-data">(.*?)</script>', re.S)
RESERVED = re.compile(r'"isReserved":(true|false)')
SINCE = re.compile(r'"since":"(\d{4}-\d{2}-\d{2})')
SELLER = '"seller":{"id":'
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def check(item: dict) -> None:
    """Set item["status"] and item["since"] from the listing's own page."""
    # robots.txt disallows listing URLs carrying ?c= or correlationId.
    url = item["url"].split("?")[0]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r:
            page = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            item["status"] = "gone"
        else:
            print(f"  {item['id']}: HTTP {e.code}, keeping last status", file=sys.stderr)
        return
    except OSError as e:
        print(f"  {item['id']}: {e}, keeping last status", file=sys.stderr)
        return
    reserved = RESERVED.search(page)
    if not reserved:
        print(f"  {item['id']}: no isReserved on the page, keeping last status", file=sys.stderr)
        return
    item["status"] = "reserved" if reserved.group(1) == "true" else "available"
    since = SINCE.search(page)
    if since:
        item["since"] = since.group(1)
    if SELLER in page:
        seller, _ = json.JSONDecoder().raw_decode(page, page.index(SELLER) + len('"seller":'))
        item["seller"] = {"id": seller["id"], "name": seller["name"],
                          "url": "https://www.marktplaats.nl" + seller["sellerProfileUrl"]}


def films_by_slug() -> dict:
    films = {}
    for line in (HERE / "films.txt").read_text().splitlines():
        slug, title, tag = line.split(" | ")
        films[slug] = {"title": title, "tag": tag}
    return films


def stars(tag: str) -> float:
    return float(tag.removeprefix("rated ")) if tag.startswith("rated") else 0


def tag_html(tag: str) -> str:
    if tag.startswith("rated"):
        return f'<span class="tag loved">{tag.removeprefix("rated ")}★</span>'
    return f'<span class="tag">{html.escape(tag)}</span>'


def card(item: dict, films: dict, today: str, chips: bool, kind: bool = False) -> str:
    bits = []
    if chips:
        for slug in item["films"]:
            film = films.get(slug, {"title": slug, "tag": "?"})
            bits.append(f'<span class="chip">{html.escape(film["title"])} {tag_html(film["tag"])}</span>')
    if (item.get("films_in_listing") or 1) >= 2:
        bits.append(f'<span class="chip dim">{item["films_in_listing"]} films in ad</span>')
    bits += [f'<span class="chip flag">{html.escape(f)}</span>' for f in item.get("flags", [])]
    days = (date.fromisoformat(today) - date.fromisoformat(item.get("since") or item["found"])).days
    badges = '<span class="badge new">&lt;1d ago</span>' if days < 1 else f'<span class="badge age">{days}d ago</span>'
    if kind and (item.get("films_in_listing") or 1) >= 2:
        badges += f'<span class="badge kind">{"set" if item["films"] else "lot"}</span>'
    if item["detour"]:
        badges += '<span class="badge detour">detour</span>'
    note = f'<p class="note">{html.escape(item["note"])}</p>' if item.get("note") else ""
    chips_html = f'<div class="chips">{"".join(bits)}</div>' if bits else ""
    return f"""<div class="item"><div class="row"><a href="{html.escape(item["url"].split("?")[0])}" target="_blank" rel="noopener">{badges}{html.escape(item["title"])}</a><span class="price">{html.escape(item["price"])}</span></div>
{chips_html}<div class="where">{html.escape(item["town"])}</div>{note}</div>"""


def section(title: str, inner: str, count: int, blurb: str = "", empty: str = "nothing yet") -> str:
    blurb = f'<p class="note">{blurb}</p>' if blurb else ""
    inner = inner or f'<p class="empty">{empty}</p>'
    return f'<section><h2>{title} <small>[{count}]</small></h2>{blurb}<div class="list">{inner}</div></section>'


def by_film(items: list, films: dict, today: str) -> tuple[str, int]:
    """Single discs grouped under the film they match, best-rated film first."""
    groups = {}
    for item in items:
        groups.setdefault(item["films"][0], []).append(item)
    rank = lambda slug: (-stars(films.get(slug, {"tag": ""})["tag"]), films.get(slug, {"title": slug})["title"])
    out = []
    for slug in sorted(groups, key=rank):
        film = films.get(slug, {"title": slug, "tag": "?"})
        cards = "".join(card(i, films, today, chips=False) for i in sorted(groups[slug], key=posted, reverse=True))
        out.append(f'<div class="film"><h3>{html.escape(film["title"])} {tag_html(film["tag"])}</h3>{cards}</div>')
    return "".join(out), len(groups)


def by_seller(items: list, films: dict, today: str, best) -> tuple[str, int]:
    """Every shown listing grouped under its seller, so one message can cover several ads."""
    groups = {}
    for item in items:
        groups.setdefault(item["seller"]["id"] if "seller" in item else item["id"], []).append(item)
    score = lambda i: best(i) if i["films"] else -1
    out = []
    for group in sorted(groups.values(), key=lambda g: (-max(map(score, g)), -len(g))):
        group.sort(key=score, reverse=True)
        seller = group[0].get("seller")
        name = (f'<a href="{html.escape(seller["url"])}" target="_blank" rel="noopener">{html.escape(seller["name"])}</a>'
                if seller else "seller unknown")
        towns = ", ".join(dict.fromkeys(i["town"] for i in group))
        count = f' <small>[{len(group)} ads]</small>' if len(group) > 1 else ""
        cards = "".join(card(i, films, today, chips=True, kind=True) for i in group)
        out.append(f'<div class="film seller"><h3>{name}{count} <span class="town">{html.escape(towns)}</span></h3>{cards}</div>')
    return "".join(out), len(groups)


def posted(item: dict) -> str:
    return item.get("since") or item["found"]


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--no-check"]
    results = json.loads(Path(args[0]).read_text())
    today = results["date"]
    for item in results["items"]:
        item["found"] = today

    carried = []
    if len(args) > 1:
        found = DATA.search(Path(args[1]).read_text())
        if found:
            fresh = {i["id"] for i in results["items"]}
            carried = [i for i in json.loads(found.group(1))["items"]
                       if i["id"] not in fresh]
    items = results["items"] + carried

    if "--no-check" not in sys.argv:
        for item in items:
            check(item)
            time.sleep(1)

    count = lambda s: sum(i.get("status", "available") == s for i in items)
    gone = count("gone")
    items = [i for i in items if i.get("status") != "gone"]
    shown = [i for i in items if i.get("status", "available") == "available"]

    films = films_by_slug()
    matched = [i for i in shown if i["films"]]
    best = lambda i: max(stars(films.get(s, {"tag": ""})["tag"]) for s in i["films"])
    sets = sorted(sorted((i for i in matched if (i.get("films_in_listing") or 1) >= 2), key=posted, reverse=True),
                  key=lambda i: (-best(i), -len(i["films"])))
    singles = [i for i in matched if i not in sets]
    priority, priority_n = by_film([i for i in singles if best(i) == 5], films, today)
    rest, rest_n = by_film([i for i in singles if best(i) < 5], films, today)
    lots = sorted((i for i in shown if not i["films"]), key=posted, reverse=True)

    by_film_body = "".join([
        section("Priority: 5★", priority, priority_n, "Films you rated 5★, including ones off your usual routes.",
                "no 5★ films on offer"),
        section("Sets", "".join(card(i, films, today, chips=True) for i in sets), len(sets)),
        section("4.5★ and below, watchlist", rest, rest_n),
        section("Collections to look into", "".join(card(i, films, today, chips=False) for i in lots), len(lots),
                "Big lots whose ads don't list every title."),
    ])
    sellers, sellers_n = by_seller(sets + singles + lots, films, today, best)
    by_seller_body = section("By seller", sellers, sellers_n,
                             "Grouped by who sells it, so one message can cover several ads. Best-rated film first, then sellers with the most ads.")
    stats = (f'<span>new <b>{len(results["items"])}</b></span><span>available <b>{len(shown)}</b></span>'
             f'<span>reserved, hidden <b>{count("reserved")}</b></span><span>sold since last run <b>{gone}</b></span>')
    fetched_at = json.loads((HERE / "listings.json").read_text())["fetched_at"]
    data = json.dumps({"fetched_at": fetched_at, "items": items}, ensure_ascii=False).replace("</", "<\\/")
    stamp = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%H:%M")
    page = (HERE / "template.html").read_text()
    for key, value in {"__DATE__": today, "__TIME__": stamp, "__STATS__": stats, "__BY_FILM__": by_film_body,
                       "__BY_SELLER__": by_seller_body,
                       "__DATA__": data}.items():
        page = page.replace(key, value)
    (HERE / "page.html").write_text(page)
    print(f"page.html: {len(results['items'])} new, {len(carried)} carried over, "
          f"{count('reserved')} reserved and hidden, {gone} gone and dropped")


if __name__ == "__main__":
    main()
