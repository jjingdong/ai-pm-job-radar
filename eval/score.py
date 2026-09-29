#!/usr/bin/env python3
"""Score Jev and the title regex against the hand labels.

Run after eval/label.py and after `radar/run.py --ids eval/labels.csv`.

Headline: the two decisions the buckets actually make, "is this a PM role?" and
"is this AI product work?". Below that, strict agreement on every label, plus every
posting Jev got wrong with the confidence it gave. Wrong at high confidence means the
question needs rewriting; wrong at low confidence means the floor is doing its job.

Usage:
  python3 eval/score.py                                   # the random sample
  python3 eval/score.py --labels eval/labels-targeted.csv --strata eval/targeted.csv \
      --out eval/results-targeted.md                      # the targeted batch, per stratum
"""
import argparse, csv, json
from pathlib import Path

ROOT = Path(__file__).parent.parent


def is_pm(x):
    return x == "pm"                       # adjacent and not_pm are both "not a PM role"


def is_ai(x):
    return {"ai_product": True, "ai_feature": True, "not_ai": False}.get(x)   # unclear -> None


def pct(k, n):
    return f"{k}/{n} ({k / n:.0%})" if n else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(ROOT / "eval" / "labels.csv"))
    ap.add_argument("--strata", help="eval/targeted.csv: also score each stratum on its own")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results.md"))
    a = ap.parse_args()

    labels = {r["id"]: r for r in csv.DictReader(open(a.labels))}
    results = {r["id"]: r for r in map(json.loads, (ROOT / "output" / "results.jsonl").read_text().splitlines())}
    ids = [i for i in labels if i in results]
    L, R = labels, results

    lines = [f"# Eval: {len(ids)} hand-labeled postings", ""]
    if len(ids) < len(labels):
        lines += [f"{len(labels) - len(ids)} labeled postings have no Jev result yet. "
                  f"Run `radar/run.py --ids {a.labels}`.", ""]

    pm_ids = [i for i in ids if is_pm(L[i]["role"])]
    ai_ids = [i for i in pm_ids if is_ai(L[i]["ai_focus"]) is not None]
    role_j = sum(is_pm(R[i]["role"]) == is_pm(L[i]["role"]) for i in ids)
    role_r = sum(is_pm(R[i]["regex_role"]) == is_pm(L[i]["role"]) for i in ids)
    ai_j = sum(is_ai(R[i]["ai_focus"]) == is_ai(L[i]["ai_focus"]) for i in ai_ids)
    ai_r = sum(is_ai(R[i]["regex_ai"]) == is_ai(L[i]["ai_focus"]) for i in ai_ids)
    lines += ["## The two decisions", "",
              "| Decision | Jev | Title regex | Scored on |", "|---|---|---|---|",
              f"| Is it a PM role? | {pct(role_j, len(ids))} | {pct(role_r, len(ids))} | all labeled postings |",
              f"| Is it AI product work? | {pct(ai_j, len(ai_ids))} | {pct(ai_r, len(ai_ids))} | "
              f"labeled PM roles with a definite AI label ({len(pm_ids) - len(ai_ids)} labeled unclear left out) |", ""]

    for title, pred, subset, test in (
        ("Regex wrong: is it a PM role?", "regex_role", ids, lambda i: is_pm(R[i]["regex_role"]) != is_pm(L[i]["role"])),
        ("Regex wrong: is it AI product work?", "regex_ai", ai_ids, lambda i: is_ai(R[i]["regex_ai"]) != is_ai(L[i]["ai_focus"])),
        ("Jev wrong: is it a PM role?", "role", ids, lambda i: is_pm(R[i]["role"]) != is_pm(L[i]["role"])),
        ("Jev wrong: is it AI product work?", "ai_focus", ai_ids, lambda i: is_ai(R[i]["ai_focus"]) != is_ai(L[i]["ai_focus"])),
    ):
        miss = [i for i in subset if test(i)]
        lines += [f"### {title} ({len(miss)})", ""]
        lines += ([f"- {L[i]['company']} · {L[i]['title'].strip()} (label: {L[i]['role'] if 'role' in pred else L[i]['ai_focus']}, "
                   f"said: {R[i][pred]})" for i in miss] or ["None."]) + [""]

    # Strict agreement, every label as written.
    strict_role = sum(R[i]["role"] == L[i]["role"] for i in ids)
    strict_ai = sum(R[i]["ai_focus"] == L[i]["ai_focus"] for i in pm_ids)
    lines += ["## Strict agreement, every label as written", "",
              f"- `role` (pm / adjacent / not_pm / unclear): Jev {pct(strict_role, len(ids))}. "
              "Most misses are Jev saying `adjacent` where the label says `not_pm`; both mean not a PM role.",
              f"- `ai_focus` (ai_product / ai_feature / not_ai / unclear): Jev {pct(strict_ai, len(pm_ids))} on labeled PM roles.", ""]
    split = [i for i in pm_ids if R[i]["ai_focus"] != L[i]["ai_focus"]]
    if split:
        lines += ["| Company | Title | Label | Jev | conf |", "|---|---|---|---|---|"]
        lines += [f"| {L[i]['company']} | {L[i]['title'].strip()} | {L[i]['ai_focus']} | {R[i]['ai_focus']} | {R[i]['ai_conf']} |"
                  for i in sorted(split, key=lambda i: -R[i]["ai_conf"])]
        lines.append("")

    ml = [i for i in pm_ids if L[i]["ml_background"] in ("true", "false")]
    if ml:
        hit = sum((R[i]["ml_background"] >= 0.5) == (L[i]["ml_background"] == "true") for i in ml)
        pos = [i for i in ml if L[i]["ml_background"] == "true"]
        caught = sum(R[i]["ml_background"] >= 0.5 for i in pos)
        lines += [f"`ml_background` at a 0.5 cut: {pct(hit, len(ml))} agree. "
                  f"{len(pos)} of {len(ml)} labeled PM roles need hands-on ML"
                  + (f"; Jev flagged {caught} of them." if pos else ", so this is only a test of false alarms."), ""]

    if a.strata:
        strata = {r["id"]: r["stratum"] for r in csv.DictReader(open(a.strata))}
        lines += ["## By stratum", "",
                  "Strata were picked from Jev's own answers (see eval/pick.py), so each is scored on its own.", "",
                  "| Stratum | Postings | PM role? | AI work? (labeled PM, definite) | Needs ML? (labeled PM) |",
                  "|---|---|---|---|---|"]
        for name in dict.fromkeys(strata.values()):
            s_ids = [i for i in ids if strata.get(i) == name]
            s_pm = [i for i in s_ids if is_pm(L[i]["role"])]
            s_ai = [i for i in s_pm if is_ai(L[i]["ai_focus"]) is not None]
            s_ml = [i for i in s_pm if L[i]["ml_background"] in ("true", "false")]
            lines.append(
                f"| {name} | {len(s_ids)} "
                f"| {pct(sum(is_pm(R[i]['role']) == is_pm(L[i]['role']) for i in s_ids), len(s_ids))} "
                f"| {pct(sum(is_ai(R[i]['ai_focus']) == is_ai(L[i]['ai_focus']) for i in s_ai), len(s_ai))} "
                f"| {pct(sum((R[i]['ml_background'] >= 0.5) == (L[i]['ml_background'] == 'true') for i in s_ml), len(s_ml))} |")
        lines.append("")

    out = Path(a.out)
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"→ {out}")


if __name__ == "__main__":
    main()
