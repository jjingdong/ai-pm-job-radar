#!/usr/bin/env python3
"""Ask Jev every question in the spec about every posting, then bucket the answers.

Usage:
  python3 radar/run.py --dry-run            # token and cost estimate, no calls
  python3 radar/run.py --sample 40          # the review checkpoint: under a cent
  python3 radar/run.py                      # everything; cached postings are free

Writes output/results.jsonl, output/results.csv, and output/summary.md.
"""
import argparse, csv, json, random, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import baseline, jev

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "data" / "cache.jsonl"


def questions_for(spec):
    """Jev takes the question map as-is. The context rides in the state, not the questions."""
    return spec["questions"]


def answer(ans, key, floors):
    """One question's answer as a label that counts, or None if it's under its floor."""
    a = ans.get(key) or {}
    if a.get("type") == "noul":
        return a.get("noul", 0) >= floors.get(key, 0.5)
    if a.get("confidence", 0) < floors.get(key, 0):
        return None
    return a.get("choice")


def bucket(ans, spec):
    floors = spec.get("floors", {})
    for b in spec["buckets"]:
        ok = True
        for key, want in b["when"].items():
            got = answer(ans, key, floors)
            if isinstance(want, bool):
                ok &= got is want
            else:
                ok &= got in want
        if ok:
            return b["name"]
    return "review"


def load_cache():
    if not CACHE.exists():
        return {}
    return {r["key"]: r["response"] for r in map(json.loads, CACHE.read_text().splitlines()) if r}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=str(ROOT / "radar" / "spec.json"))
    ap.add_argument("--input", default=str(ROOT / "data" / "postings.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--sample", type=int, help="random N postings (seeded, so reruns match)")
    ap.add_argument("--ids", help="file of posting ids to run, one per line (e.g. eval/labels.csv)")
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    spec = json.loads(Path(a.spec).read_text())
    postings = [json.loads(l) for l in Path(a.input).read_text().splitlines() if l.strip()]
    if a.ids:
        rows = Path(a.ids).read_text().splitlines()
        wanted = {r.split(",")[0].strip() for r in rows if r and not r.startswith("id")}
        postings = [p for p in postings if p["id"] in wanted]
    elif a.sample and a.sample < len(postings):
        postings = random.Random(7).sample(postings, a.sample)

    model, qs = spec["model"], questions_for(spec)
    jobs = [(p, jev.state_for(p, spec["context"])) for p in postings]
    cache = load_cache()
    todo = [(p, s) for p, s in jobs if jev.cache_key(model, qs, s) not in cache]

    if a.dry_run:
        chars = sum(len(json.dumps(s)) + len(json.dumps(qs)) for _, s in todo)
        tokens = chars / 4                       # rough: ~4 characters per token
        print(f"{len(jobs)} postings, {len(todo)} not cached · ~{tokens:,.0f} input tokens · "
              f"~${tokens * jev.PRICE_PER_M_INPUT / 1e6:.4f}")
        print(json.dumps(todo[0][1] if todo else jobs[0][1], indent=1)[:1500])
        return

    key = jev.api_key() if todo else None
    t0, errors = time.monotonic(), []
    if todo:
        with ThreadPoolExecutor(a.concurrency) as ex, open(CACHE, "a") as cf:
            futs = {ex.submit(jev.ask, key, model, qs, s): s for _, s in todo}
            for i, f in enumerate(as_completed(futs), 1):
                s = futs[f]
                try:
                    r = f.result()
                except RuntimeError as e:
                    errors.append(str(e))
                    continue
                k = jev.cache_key(model, qs, s)
                cache[k] = r
                cf.write(json.dumps({"key": k, "response": r}) + "\n")
                if i % 50 == 0:
                    print(f"  {i}/{len(todo)}", file=sys.stderr)
    seconds = time.monotonic() - t0

    results, spent, tokens, served_by = [], 0.0, 0, set()
    fresh = {jev.cache_key(model, qs, s) for _, s in todo}
    for p, s in jobs:
        k = jev.cache_key(model, qs, s)
        r = cache.get(k)
        if not r:
            continue
        if k in fresh:
            spent += jev.cost(r)
            tokens += r.get("usage", {}).get("input_tokens", 0)
        served_by.add(r.get("model", "?"))
        ans = r["answers"]
        results.append({
            "id": p["id"], "company": p["company"], "title": p["title"], "location": p["location"],
            "remote": p["remote"], "pay": p["pay"], "url": p["url"],
            "bucket": bucket(ans, spec),
            "role": ans["role"]["choice"], "role_conf": round(ans["role"].get("confidence", 0), 2),
            "ai_focus": ans["ai_focus"]["choice"], "ai_conf": round(ans["ai_focus"].get("confidence", 0), 2),
            "ml_background": round(ans["ml_background"]["noul"], 2),
            "regex_role": baseline.role(p["title"]), "regex_ai": baseline.ai_focus(p["title"]),
            "latency_ms": r.get("latency_ms"),
        })

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "results.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    if results:
        with open(out / "results.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(results[0]))
            w.writeheader()
            w.writerows(results)

    counts = {}
    for r in results:
        counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1
    flips = [r for r in results if r["role"] != r["regex_role"]]
    lat = sorted(r["latency_ms"] for r in results if r.get("latency_ms"))
    head = (f"{len(results)} postings · {len(todo) - len(errors)} new calls in {seconds:.1f}s · "
            f"${spent:.4f} · {tokens:,} input tokens · model {', '.join(sorted(served_by))}")
    if lat:
        head += f" · median latency {lat[len(lat) // 2]} ms"

    md = [f"# Run summary", "", head, "", "## Buckets", ""]
    md += [f"- **{b}**: {n}" for b, n in sorted(counts.items(), key=lambda x: -x[1])]
    md += ["", f"## Where Jev and the title regex disagree on `role` ({len(flips)})", "",
           "| Company | Title | Jev | conf | Regex |", "|---|---|---|---|---|"]
    md += [f"| {r['company']} | {r['title']} | {r['role']} | {r['role_conf']} | {r['regex_role']} |"
           for r in flips[:40]]
    for name in ("ai_pm", "ai_pm_ml_required"):
        rows = [r for r in results if r["bucket"] == name]
        md += ["", f"## {name} ({len(rows)})", "", "| Company | Title | Remote | Pay |", "|---|---|---|---|"]
        md += [f"| {r['company']} | [{r['title']}]({r['url']}) | {r['remote']} | {r['pay']} |" for r in rows]
    (out / "summary.md").write_text("\n".join(md) + "\n")

    print(head)
    for b, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {b:20s} {n}")
    print(f"  role disagreements with regex: {len(flips)}")
    if errors:
        print(f"{len(errors)} calls failed; first: {errors[0]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
