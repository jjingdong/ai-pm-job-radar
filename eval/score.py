#!/usr/bin/env python3
"""Score Jev and the title regex against the hand labels.

Run after eval/label.py and after `radar/run.py --ids eval/labels.csv`.
Reports agreement per question, where each one was wrong, and what confidence
the wrong Jev answers came with. That last part is what sets the floors in spec.json.

Usage: python3 eval/score.py
"""
import csv, json
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main():
    labels = {r["id"]: r for r in csv.DictReader((ROOT / "eval" / "labels.csv").open())}
    results = {r["id"]: r for r in map(json.loads, (ROOT / "output" / "results.jsonl").read_text().splitlines())}
    ids = [i for i in labels if i in results]
    missing = len(labels) - len(ids)

    lines = [f"# Eval: {len(ids)} hand-labeled postings", ""]
    if missing:
        lines += [f"{missing} labeled postings have no Jev result yet. Run `radar/run.py --ids eval/labels.csv`.", ""]

    lines += ["| Question | Jev agrees | Title regex agrees | Scored on |", "|---|---|---|---|"]
    wrong = {}
    for q, jk, rk, subset in [("role", "role", "regex_role", ids),
                              ("ai_focus", "ai_focus", "regex_ai", [i for i in ids if labels[i]["role"] == "pm"])]:
        j = sum(results[i][jk] == labels[i][q] for i in subset)
        if q == "ai_focus":
            # The regex has no ai_feature option; count it right when it says ai_product for either AI label.
            r = sum((results[i][rk] == "ai_product") == (labels[i][q] in ("ai_product", "ai_feature")) for i in subset)
        else:
            r = sum(results[i][rk] == labels[i][q] for i in subset)
        wrong[q] = [i for i in subset if results[i][jk] != labels[i][q]]
        n = len(subset) or 1
        lines.append(f"| `{q}` | {j}/{len(subset)} ({j / n:.0%}) | {r}/{len(subset)} ({r / n:.0%}) | "
                     f"{'all' if subset is ids else 'labeled PM roles'} |")
    lines += ["", "The regex has no `ai_feature` option, so for `ai_focus` it is scored on AI vs. not AI only, "
              "a looser test than Jev gets.", ""]

    for q, conf in (("role", "role_conf"), ("ai_focus", "ai_conf")):
        lines += [f"## Jev wrong on `{q}` ({len(wrong[q])})", ""]
        if not wrong[q]:
            lines += ["None.", ""]
            continue
        lines += ["| Company | Title | Label | Jev | conf | Note |", "|---|---|---|---|---|---|"]
        for i in sorted(wrong[q], key=lambda i: -results[i][conf]):
            lines.append(f"| {labels[i]['company']} | {labels[i]['title']} | {labels[i][q]} | "
                         f"{results[i][q]} | {results[i][conf]} | {labels[i]['note']} |")
        lines.append("")

    ml = [i for i in ids if labels[i]["ml_background"] in ("true", "false")]
    if ml:
        hit = sum((results[i]["ml_background"] >= 0.5) == (labels[i]["ml_background"] == "true") for i in ml)
        lines += [f"`ml_background` at a 0.5 cut: {hit}/{len(ml)} agree with the labels.", ""]

    out = ROOT / "eval" / "results.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"→ {out}")


if __name__ == "__main__":
    main()
