#!/usr/bin/env python3
"""Turn the latest run into the static demo page at site/index.html.

Usage: python3 radar/build_site.py

Reads output/results.jsonl, output/run.json, and data/fetch-stats.json. Every row is
written into the HTML, so the page works without a server, an API key, or JavaScript.
Only titles, companies, locations, pay, and Jev's labels are published, never the
posting text.

It refuses to build rather than publish something wrong: a company outside the public
list (so a private boards.local.json run can't leak), an empty run, or a day when most
boards failed. In those cases the last good page stays up.
"""
import argparse, datetime, html, json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
HERE = Path(__file__).parent

VIEWS = {  # bucket -> tab
    "ai_pm": "ai", "ai_pm_ml_required": "ai", "pm_ai_features": "feature",
    "review": "review", "pm_non_ai": "other", "not_pm": "not",
}
JEV_LABELS = {
    "ai_pm": "AI product", "ai_pm_ml_required": "AI product, needs ML", "pm_ai_features": "AI features",
    "pm_non_ai": "PM, no AI", "review": "Unsure",
}
MIN_BOARD_SHARE = 0.5


def esc(value):
    return html.escape(str(value), quote=True)


def public_companies():
    boards = json.loads((HERE / "boards.json").read_text())
    return {name for m in boards.values() if isinstance(m, dict) for name in m}


def rule_label(r):
    """What the title rule in baseline.py says about the same posting."""
    if r["regex_role"] != "pm":
        return "Not PM"
    return "AI PM" if r["regex_ai"] == "ai_product" else "PM, no AI"


def jev_label(r):
    if r["bucket"] == "not_pm":
        return "Adjacent role" if r["role"] == "adjacent" else "Not PM"
    return JEV_LABELS[r["bucket"]]


def confidence(r):
    if r["bucket"] == "not_pm":
        return r["role_conf"]
    if r["bucket"] == "review":
        return min(r["role_conf"], r["ai_conf"])
    return r["ai_conf"]


def disagrees(r):
    rule, view = rule_label(r), VIEWS[r["bucket"]]
    if view in ("ai", "feature"):
        return rule != "AI PM"
    if view == "other":
        return rule != "PM, no AI"
    if view == "not":
        return rule != "Not PM"
    return False


def short_location(location):
    places = [p.strip() for p in location.split("|") if p.strip()]
    if len(places) <= 2:
        return esc(" · ".join(places)) or "Not stated"
    return (f'<span title="{esc(" · ".join(places))}">{esc(" · ".join(places[:2]))} '
            f'<span class="more">+{len(places) - 2} more</span></span>')


def row(r):
    view, differs = VIEWS[r["bucket"]], disagrees(r)
    remote = r["remote"] == "remote"
    url = r["url"] if r["url"].startswith(("https://", "http://")) else ""
    title = f'<a href="{esc(url)}" rel="noopener noreferrer" target="_blank">{esc(r["title"])}</a>' if url else esc(r["title"])
    pay = esc(r["pay"]) if r["pay"] != "not stated" else '<span class="quiet">Not stated</span>'
    tag = '<span class="tag">Remote</span>' if remote else ""
    search = esc(f'{r["title"]} {r["company"]} {r["location"]}'.lower())
    return (
        f'<tr data-view="{view}" data-company="{esc(r["company"])}" data-remote="{int(remote)}" '
        f'data-differs="{int(differs)}" data-search="{search}"{"" if view == "ai" else " hidden"}>'
        f'<td data-label="Company" class="company">{esc(r["company"])}</td>'
        f'<td data-label="Role" class="role">{title}</td>'
        f'<td data-label="Location">{short_location(r["location"])}{tag}</td>'
        f'<td data-label="Pay" class="num">{pay}</td>'
        f'<td data-label="Jev">{esc(jev_label(r))} <span class="conf">{confidence(r):.2f}</span></td>'
        f'<td data-label="Title filter" class="{"differs" if differs else "agrees"}">{esc(rule_label(r))}</td>'
        "</tr>"
    )


def funnel(stats, ai_total):
    if not stats:
        return ""
    steps = [
        (f'{stats["open_roles"]:,}', f'open roles at {stats["boards_ok"]} companies'),
        (f'{stats["kept"]:,}', "with a product title"),
        (f'{stats["unique"]:,}', "unique postings Jev read"),
        (f"{ai_total:,}", "with AI work"),
    ]
    items = "".join(f"<li><b>{n}</b> {label}</li>" for n, label in steps)
    return f'<ol class="funnel" aria-label="How this list was narrowed">{items}</ol>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "output" / "results.jsonl"))
    ap.add_argument("--run", default=str(ROOT / "output" / "run.json"))
    ap.add_argument("--stats", default=str(ROOT / "data" / "fetch-stats.json"))
    ap.add_argument("--out", default=str(ROOT / "site"))
    ap.add_argument("--as-of", help="YYYY-MM-DD to show as the update date; defaults to today (UTC)")
    a = ap.parse_args()

    results = [json.loads(l) for l in Path(a.results).read_text().splitlines() if l.strip()]
    if not results:
        sys.exit("No results to publish; keeping the last good page.")
    private = {r["company"] for r in results} - public_companies()
    if private:
        sys.exit(f"{len(private)} companies aren't in radar/boards.json. "
                 "Refusing to publish a run from a private list.")

    stats_path, run_path = Path(a.stats), Path(a.run)
    stats = json.loads(stats_path.read_text()) if stats_path.exists() else None
    run = json.loads(run_path.read_text()) if run_path.exists() else None
    if stats and stats["boards_ok"] < stats["boards_total"] * MIN_BOARD_SHARE:
        sys.exit(f'Only {stats["boards_ok"]}/{stats["boards_total"]} boards answered; keeping the last good page.')

    results.sort(key=lambda r: (r["company"].lower(), r["title"].lower()))
    counts = {v: 0 for v in ("ai", "feature", "review", "other", "not")}
    for r in results:
        counts[VIEWS[r["bucket"]]] += 1
    ai_rows = [r for r in results if VIEWS[r["bucket"]] in ("ai", "feature")]
    found = sum(rule_label(r) == "AI PM" for r in ai_rows)

    as_of = a.as_of or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    day = datetime.date.fromisoformat(as_of)
    run_note = ""
    if run:
        models = ", ".join(run["models"])
        run_note = (f'Latest run: {run["new_calls"]:,} new postings sent to Jev, '
                    f'${run["spent"]:.3f}, model {esc(models)}.')

    companies = "".join(f'<option value="{esc(c)}">{esc(c)}</option>'
                        for c in sorted({r["company"] for r in results}, key=str.lower))
    page = (HERE / "site_template.html").read_text()
    for key, value in {
        "UPDATED_ISO": as_of,
        "UPDATED": f"{day:%B} {day.day}, {day.year}",
        "AI_TOTAL": f"{len(ai_rows):,}",
        "RULE_FOUND": f"{found:,}",
        "RULE_MISSED": f"{len(ai_rows) - found:,}",
        "FUNNEL": funnel(stats, len(ai_rows)),
        "COUNT_AI": f'{counts["ai"]:,}',
        "COUNT_FEATURE": f'{counts["feature"]:,}',
        "COUNT_REVIEW": f'{counts["review"]:,}',
        "COUNT_OTHER": f'{counts["other"]:,}',
        "COUNT_NOT": f'{counts["not"]:,}',
        "COMPANIES": companies,
        "ROWS": "\n".join(row(r) for r in results),
        "RUN_NOTE": run_note,
    }.items():
        page = page.replace(f"%%{key}%%", value)
    if "%%" in page.replace("100%%", ""):
        sys.exit("Template placeholder left unfilled.")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page)
    print(f"{out / 'index.html'}: {len(results)} rows, {len(ai_rows)} with AI work, "
          f"title rule found {found}, updated {as_of}")


if __name__ == "__main__":
    main()
