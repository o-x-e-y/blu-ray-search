# Deals check

You check second-hand Blu-ray ads (Dutch, from Marktplaats) that a script
shortlisted as cheap ways to get films the user wants. The user plays discs on
a European (region B) Blu-ray player and a 4K UHD player.

Each line of your input file is:

`id | seller | ad title | description (long ones excerpted with […]) | films: slug = Title (bd|4k) | listed price (script flags), delivery, place | matcher note`

The listed price was read by a script. "bieden vanaf €N" is a minimum bid, and
"price from text" means the script took the lowest € amount in the description,
which is often wrong for catalogue ads ("prijzen van €1 tot €50").

For EVERY line write one JSON object per line to your output file:

{"id": "m123", "drop": false, "why": "short reason", "price": null, "format": {"slug": "bd"}, "drop_films": [], "flags": []}

- **drop: true** when the ad is no good:
  - region A only (regio A, region A, zone A, US Blu-ray that is region locked).
    A 4K UHD disc is region-free, so a 4K edition is never dropped for this; in a
    4K + Blu-ray combo only the Blu-ray can be locked and the 4K still counts.
  - severe damage: werkt niet, hapert, springt, kapot, gebroken, diepe krassen,
    beschadigde disc, disc rot.
  - disc missing: disc ontbreekt, alleen hoes/cover, zonder disc, lege doos.
  - not a real sale: verkocht, gereserveerd, gezocht (wanted ad), ruilen only,
    digital code only, rental copy without disc.
  - DVD only, or the matched film is clearly not the one in the ad (wrong year,
    remake, different film with the same name).
- **drop_films**: slugs from the films list that this ad doesn't actually offer
  (a catalogue where that title isn't listed, or is a DVD, or is listed as sold),
  or that cost more than €6 (Blu-ray) / €20 (4K) each in a per-title price list.
  If every film would be dropped, set drop: true instead.
- **price**: the real total in euros for the films you keep, when the listed
  price isn't it. For example: per-title prices in a catalogue ("Heat — € 5"),
  "€3 per stuk" times the kept films, or a price stated in the text of a "bieden"
  ad. Use null when the listed price is right. Ignore multi-buy deals
  ("4 halen = 3 betalen") for the price, and flag them instead.
- **format**: for each kept slug, "4k" if the ad sells that film as 4K UHD
  (4K only or 4K + Blu-ray), otherwise "bd". Mentioning that the seller also has
  4K titles doesn't make a title 4K.
- **flags**, any of:
  - "wear": light scratches, gebruikssporen, a damaged case, a missing slipcover
  - "region?": a US/import Blu-ray with no region stated
  - "multibuy": the seller offers a quantity discount (say which in why)
  - "steelbook"
  - "sealed": nieuw in folie
- When something is unclear, keep the ad, and say what's unclear in why.

Keep why under 15 words. Write the output with the Write tool in one go, or in
a few appends if it's long, and make sure every input id appears exactly once.
Don't edit any other file.
