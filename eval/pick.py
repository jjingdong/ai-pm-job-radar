#!/usr/bin/env python3
"""Pick a targeted batch to label, aimed at what the random 40 couldn't test.

The random sample had no PM roles labeled not_ai and none that needed hands-on ML,
so it only tested one direction. This batch fills those gaps:

  not_ai      10  Jev says PM, not AI. Is it right that they aren't AI?
  ai_feature   4  Jev says PM on a product adding AI. Is it over-calling AI?
  ml           8  every posting Jev says needs ML, plus PM titles that look ML-heavy
                  (research, models, ML, applied science), picked by title, not score
  review       8  postings under a floor, for tuning the floors

Most strata are chosen from Jev's own answers, so score them per stratum, not as one
accuracy number. Already-labeled postings are skipped. Order is shuffled so the labeler
can't tell which stratum a posting came from.

Needs a full run first: python3 radar/run.py (cached, free after the first time).
Usage: python3 eval/pick.py            writes eval/targeted.csv
"""
import argparse, csv, json, random, re
from pathlib import Path

ROOT = Path(__file__).parent.parent
ML_TITLE = re.compile(r"research|\bmodel|\bml\b|machine learning|applied science", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "output" / "results.jsonl"), help="a full run's results.jsonl")
    a = ap.parse_args()
    results = [json.loads(l) for l in Path(a.results).read_text().splitlines() if l.strip()]
    if len(results) < 100:
        raise SystemExit(f"{a.results} looks like a sample run. Run `python3 radar/run.py` first.")
    labeled = {r["id"] for r in csv.DictReader((ROOT / "eval" / "labels.csv").open())}
    pool = [r for r in results if r["id"] not in labeled]
    rng = random.Random(42)

    def take(rows, n):
        return rng.sample(rows, min(n, len(rows)))

    ml_req = [r for r in pool if r["bucket"] == "ai_pm_ml_required"]
    ml_title = sorted((r for r in pool if r["role"] == "pm" and ML_TITLE.search(r["title"]) and r not in ml_req),
                      key=lambda r: -r["ml_background"])
    picked = {
        "not_ai": take([r for r in pool if r["bucket"] == "pm_non_ai"], 10),
        "ai_feature": take([r for r in pool if r["bucket"] == "pm_ai_features"], 4),
        "ml": (ml_req + ml_title)[:8],
        "review": take([r for r in pool if r["bucket"] == "review"], 8),
    }
    rows = [(r["id"], stratum, r["company"], r["title"].strip()) for stratum, rs in picked.items() for r in rs]
    rng.shuffle(rows)

    out = ROOT / "eval" / "targeted.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "stratum", "company", "title"])
        w.writerows(rows)
    for stratum, rs in picked.items():
        print(f"  {stratum:11s} {len(rs)}")
    print(f"{len(rows)} postings → {out}")


if __name__ == "__main__":
    main()
