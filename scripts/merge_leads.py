#!/usr/bin/env python3
"""Merge per-city scrape CSVs into one deduped, city-tagged lead list (stdlib only).

Made for the Rabat/Temara beauty-salon campaign but works for any pair of city runs
produced by scrape.py (ideally with --fields "...,place_id" for exact deduping; falls
back to title+address otherwise):

    python3 scripts/merge_leads.py rabat.csv temara.csv -o leads.csv
"""
import argparse, csv, json, os, re, sys

FINAL = ["city", "title", "category", "phone", "emails", "website",
         "instagram", "facebook", "linkedin", "address", "review_rating", "review_count"]

CITY_HINTS = [  # substring of address (lowercased) -> city tag
    (("témara", "temara", "harhoura"), "Temara"),
    (("rabat",), "Rabat"),
    (("salé", "sale "), "Salé"),
    (("skhirat", "skhirate"), "Skhirat"),
]


def clean_emails(v):
    """Normalize the emails field to a comma-joined list (raw may be JSON-ish)."""
    if not v:
        return ""
    v = v.strip()
    if v.startswith("["):
        try:
            lst = json.loads(v.replace("'", '"'))
            return ", ".join(e for e in lst if e)
        except Exception:
            v = v.strip("[]").replace("'", "").replace('"', "")
    return ", ".join(p.strip() for p in re.split(r"[,;]", v) if p.strip())


def tag_city(address, fallback):
    a = (address or "").lower()
    for hints, name in CITY_HINTS:
        if any(h in a for h in hints):
            return name
    return fallback


def main():
    ap = argparse.ArgumentParser(description="Merge + dedupe per-city scrape CSVs into one lead list.")
    ap.add_argument("csvs", nargs="+", help="input CSVs from scrape.py, one per city")
    ap.add_argument("--city", action="append", default=None,
                    help="fallback city tag for the Nth input (default: input file name stem)")
    ap.add_argument("-o", "--out", default="leads.csv", help="output CSV (default: leads.csv)")
    a = ap.parse_args()

    rows, seen = [], set()
    per_source = {}
    for i, path in enumerate(a.csvs):
        fallback = (a.city[i] if a.city and i < len(a.city)
                    else os.path.splitext(os.path.basename(path))[0].capitalize())
        if not os.path.exists(path):
            print(f"! missing: {path} (skipped)", file=sys.stderr)
            continue
        with open(path, newline="", encoding="utf-8") as f:
            src = list(csv.DictReader(f))
        per_source[fallback] = len(src)
        for r in src:
            key = (r.get("place_id") or "").strip() or (
                (r.get("title", "").strip().lower(), r.get("address", "").strip().lower()))
            if not key or key in seen:
                continue
            seen.add(key)
            row = {k: r.get(k, "").strip() for k in FINAL if k != "city"}
            row["city"] = tag_city(r.get("address"), fallback)
            row["emails"] = clean_emails(r.get("emails", ""))
            rows.append(row)

    def rc(r):
        try:
            return int(float(r.get("review_count") or 0))
        except Exception:
            return 0

    # Strongest prospects first within each city (most-reviewed = most established).
    rows.sort(key=lambda r: (r["city"], -rc(r), r["title"]))

    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FINAL)
        w.writeheader()
        w.writerows(rows)

    cities, cats = {}, {}
    for r in rows:
        cities[r["city"]] = cities.get(r["city"], 0) + 1
        cats[r["category"] or "(none)"] = cats.get(r["category"] or "(none)", 0) + 1
    stats = {
        "total": len(rows),
        "raw_rows_per_source": per_source,
        "by_city": cities,
        "with_phone": sum(1 for r in rows if r["phone"]),
        "with_email": sum(1 for r in rows if r["emails"]),
        "with_website": sum(1 for r in rows if r["website"]),
        "with_instagram": sum(1 for r in rows if r["instagram"]),
        "with_any_social": sum(1 for r in rows if r["instagram"] or r["facebook"] or r["linkedin"]),
        "top_categories": sorted(cats.items(), key=lambda kv: -kv[1])[:8],
        "out": a.out,
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
