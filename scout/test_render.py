"""The page's max price per film (6 euros a Blu-ray, 24 a 4K here) mustn't bury sets that are cheap per film.

    .venv/bin/python -m unittest test_render
"""
import json
import unittest
from pathlib import Path

from render import price_basis

HERE = Path(__file__).parent
NL = HERE / "nl"
BD, UHD = 6, 24
FILMS = {
    "the-matrix": {"title": "The Matrix (1999)", "tag": "watchlist"},
    "district-9": {"title": "District 9 (2009)", "tag": "watchlist"},
    "life-of-pi": {"title": "Life of Pi (2012)", "tag": "watchlist"},
    "taxi-driver": {"title": "Taxi Driver (1976)", "tag": "rated 4.0"},
    "conan-the-barbarian": {"title": "Conan the Barbarian (1982)", "tag": "watchlist"},
    "heat-1995": {"title": "Heat (1995)", "tag": "watchlist"},
    "dune-part-two": {"title": "Dune: Part Two (2024)", "tag": "rated 5.0"},
}


def ad(title, description, price, films, in_listing, flags=()):
    return {"title": title, "description": description, "price": price, "films": films,
            "films_in_listing": in_listing, "flags": list(flags)}


def too_dear(item, films=FILMS):
    """The page's rule (template.html, tooDear) at 6/24."""
    cost, bd, uhd = price_basis(item, films)
    return cost is not None and cost > bd * BD + uhd * UHD


class Sets(unittest.TestCase):
    # Real ads from the 2026-11-13 nationwide run.
    def test_per_piece_price_after_the_amount(self):
        item = ad("Originele Blu-rays 24 films", "24 originele films op blu-ray allemaal nederlands ondertiteld "
                  "3,50 euro per stuk alles in 1 koop voor 60 euro.", "€60", ["the-matrix"], 24)
        self.assertEqual(price_basis(item, FILMS), (3.5, 1, 0))
        self.assertFalse(too_dear(item))

    def test_per_piece_price_in_a_list(self):
        item = ad("Meerdere titels 11 blue ray", "Elf blu-rays: - Inception - District 9 - Life of Pi - Underworld "
                  "(blu-ray + dvd) € 5 per stuk, alle elf samen € 40.", "€40", ["district-9", "life-of-pi"], 11)
        self.assertEqual(price_basis(item, FILMS)[0], 10)
        self.assertFalse(too_dear(item))

    def test_per_piece_price_before_the_amount(self):
        item = ad("5 Steelbook Editions", "dead in tombstone, conan the barbarian, hell ride, taxi driver, en mail. "
                  "Per stuk kosten ze 10 euro, of koop alle 5 voor 25 euro.", "€25",
                  ["taxi-driver", "conan-the-barbarian"], 5)
        self.assertEqual(price_basis(item, FILMS)[0], 20)
        self.assertTrue(too_dear(item), "two films at 10 euros each are over 6")

    def test_per_piece_price_by_group(self):
        item = ad("Blu Rays Arrow Video, Eureka", "Nog beschikbaar: 88 Films €15,- p.s. 🔹Martial Club 🔹Twin Dragons "
                  "Eureka Entertainment €20,- p.s. 🔹M 🔹White Dog Overig €5,- p.s. NL ondertiteld 🔹Hook 🔹Heat "
                  "🔹Titanic", "zie omschrijving", ["heat-1995"], 12)
        self.assertEqual(price_basis(item, FILMS)[0], 5)

    def test_per_title_prices(self):
        item = ad("Blu-ray collectie", "Apocalypse Now — € 16,- ​Heat — € 5,- ​Jaws — € 18,-", "€1",
                  ["heat-1995"], 40)
        self.assertEqual(price_basis(item, FILMS)[0], 1, "the listed price wins when it is lower")
        item["price"] = "zie omschrijving"
        self.assertEqual(price_basis(item, FILMS)[0], 5)

    def test_whole_set_priced_per_listed_film(self):
        item = ad("Matrix, District 9, Life of Pi", "Drie blu-rays, samen te koop.", "€18",
                  ["the-matrix", "district-9", "life-of-pi"], 3)
        self.assertFalse(too_dear(item))
        item["price"] = "€18,50"
        self.assertTrue(too_dear(item))

    def test_4k_set_uses_the_4k_max(self):
        item = ad("Dune Part Two 4K UHD + Heat 4K", "Beide als nieuw.", "€45", ["dune-part-two", "heat-1995"], 2)
        self.assertEqual(price_basis(item, FILMS), (45, 0, 2))
        self.assertFalse(too_dear(item))

    def test_unpriced_ads_and_lots_stay(self):
        self.assertFalse(too_dear(ad("Blu-ray films", "Veel titels.", "bieden", ["the-matrix"], 30)))
        self.assertEqual(price_basis(ad("Doos blu-rays", "", "€80", [], 100), FILMS), (80, 0, 0))


@unittest.skipUnless((NL / "results.json").exists() and list(NL.glob("deals-check-*.jsonl")), "no nationwide run")
class CheckedSets(unittest.TestCase):
    """Every set the Sonnet check priced at 6/24 or less per film stays on the page."""

    def test_no_cheap_checked_set_is_buried(self):
        import render
        films = render.films_by_slug()
        results = {i["id"]: i for i in json.loads((NL / "results.json").read_text())["items"]}
        listings = {l["id"]: l for l in json.loads((NL / "listings.json").read_text())}
        text = {}
        for f in sorted(NL.glob("chunk-*.txt")) + [NL / "full.txt"]:
            for line in f.read_text().splitlines():
                id_, _, desc = (line.split(" | ", 2) + ["", ""])[:3]
                text[id_] = desc
        buried, checked = [], 0
        for f in NL.glob("deals-check-*.jsonl"):
            for line in filter(str.strip, f.read_text().splitlines()):
                c = json.loads(line)
                match = results[c["id"]]
                if c["drop"] or (match["films_in_listing"] or 1) < 2:
                    continue
                item = listings[c["id"]] | match | {"description": text.get(c["id"], "")}
                kept = [s for s in match["films"] if s in films and s not in c.get("drop_films", [])]
                real = c["price"] if c.get("price") is not None else render.listed_price(item["price"])
                fmt = c.get("format", {})
                if real is None or not kept or real > sum(UHD if fmt.get(s) == "4k" else BD for s in kept):
                    continue
                checked += 1
                if too_dear(item, films):
                    buried.append(f'{c["id"]} {item["title"]!r}: €{real:g} for {len(kept)}, page has {price_basis(item, films)}')
        self.assertGreater(checked, 0)
        self.assertEqual(buried, [], f"{len(buried)} of {checked} cheap sets would be under 'expensive'")


if __name__ == "__main__":
    unittest.main()
