#!/usr/bin/env python3
"""Hand-label a fixed random sample of postings. These labels are the ground truth.

Labels are made by a person reading the posting, before looking at what Jev said.
Nothing here calls Jev.

Usage: python3 eval/label.py --n 40
Resumable: already-labeled ids are skipped. Writes eval/labels.csv.
"""
import argparse, csv, json, random, textwrap
from pathlib import Path

ROOT = Path(__file__).parent.parent
LABELS = ROOT / "eval" / "labels.csv"
FIELDS = ["id", "company", "title", "role", "ai_focus", "ml_background", "note"]
ROLE = {"p": "pm", "a": "adjacent", "n": "not_pm", "u": "unclear"}
AI = {"a": "ai_product", "f": "ai_feature", "n": "not_ai", "u": "unclear"}
YN = {"y": "true", "n": "false"}


def pick(prompt, options):
    while True:
        v = input(prompt).strip().lower()
        if v in options:
            return options[v]
        if v == "q":
            raise KeyboardInterrupt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--input", default=str(ROOT / "data" / "postings.jsonl"))
    a = ap.parse_args()

    postings = [json.loads(l) for l in Path(a.input).read_text().splitlines() if l.strip()]
    sample = random.Random(42).sample(postings, min(a.n, len(postings)))
    done = set()
    if LABELS.exists():
        done = {r["id"] for r in csv.DictReader(LABELS.open())}
    new = not LABELS.exists()
    with LABELS.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, p in enumerate(sample, 1):
            if p["id"] in done:
                continue
            print("\n" + "=" * 80)
            print(f"[{i}/{len(sample)}] {p['company']} · {p['title']}")
            print(f"{p['location']} · {p['remote']} · pay {p['pay']}\n{p['url']}\n")
            print(textwrap.fill(p["body"][:2500], 100))
            try:
                role = pick("\nrole?  (p)m  (a)djacent  (n)ot PM  (u)nclear  (q)uit: ", ROLE)
                ai = pick("AI?    (a)i product  ai (f)eature  (n)ot AI  (u)nclear: ", AI) if role == "pm" else ""
                ml = pick("needs hands-on ML background?  (y)es  (n)o: ", YN) if role == "pm" else ""
                note = input("note (optional): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nSaved. Rerun to continue.")
                return
            w.writerow(dict(id=p["id"], company=p["company"], title=p["title"],
                            role=role, ai_focus=ai, ml_background=ml, note=note))
            f.flush()
    print(f"\nAll {len(sample)} labeled → {LABELS}")


if __name__ == "__main__":
    main()
