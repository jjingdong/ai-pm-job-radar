#!/usr/bin/env python3
"""Fetch every open role from public ATS job boards and keep the ones worth asking Jev about.

Stage 1 is code, not a model: a loose title filter keeps anything that could be a product
role ("product", "PM", "GM") and drops the thousands of engineering, sales, and ops roles
that obviously aren't. Jev only sees what survives, so it judges meaning, not volume.

Facts are computed here and handed to Jev as fields: pay range, remote flag, text length.
Jev is bad at arithmetic and string matching; code is good at both.

Usage: python3 radar/fetch.py --out data/postings.jsonl
"""
import argparse, hashlib, html, json, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
UA = {"User-Agent": "ai-pm-job-radar (github.com/jjingdong)"}
URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{}/jobs?content=true",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{}?includeCompensation=true",
    "lever": "https://api.lever.co/v0/postings/{}?mode=json",
}
# Loose on purpose: stage 1 should never drop a real PM role. Jev handles the false positives.
MAYBE_PRODUCT = re.compile(r"\bproduct\b|\bpm\b|\bgm\b|general manager", re.I)
BODY_CHARS = 6000   # enough for responsibilities and requirements; keeps each request small


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def text(s):
    s = html.unescape(s or "")            # Greenhouse double-encodes its HTML
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def normalize(ats, company, j):
    if ats == "greenhouse":
        return dict(company=company, title=j.get("title", ""), location=(j.get("location") or {}).get("name", ""),
                    url=j.get("absolute_url", ""), body=text(j.get("content")))
    if ats == "ashby":
        return dict(company=company, title=j.get("title", ""), location=j.get("location", ""),
                    url=j.get("jobUrl", ""), body=text(j.get("descriptionHtml") or j.get("descriptionPlain")),
                    remote_flag=j.get("isRemote"))
    if ats == "lever":
        cats = j.get("categories") or {}
        lists = " ".join(f"{x.get('text', '')} {x.get('content', '')}" for x in j.get("lists") or [])
        return dict(company=company, title=j.get("text", ""), location=cats.get("location", ""),
                    url=j.get("hostedUrl", ""), body=text(f"{j.get('description', '')} {lists}"))


def pay_range(body):
    """Lowest and highest annual USD figure in the posting, in $K. Code, not Jev: it's arithmetic."""
    nums = [int(a) * 1000 + int(b) for a, b in re.findall(r"\$\s?(\d{2,3}),(\d{3})\b", body)]
    nums += [int(k) * 1000 for k in re.findall(r"\$\s?(\d{2,3})\s?[kK]\b", body)]
    nums = [n // 1000 for n in nums if 50_000 <= n <= 1_500_000]
    return (min(nums), max(nums)) if nums else (None, None)


def facts(p):
    lo, hi = pay_range(p["body"])
    remote = p.pop("remote_flag", None)
    if remote is None:
        remote = bool(re.search(r"\bremote\b", p["location"], re.I))
    p["pay"] = f"${lo}K to ${hi}K" if lo else "not stated"
    p["remote"] = "remote" if remote else "not remote"
    p["body"] = p["body"][:BODY_CHARS]
    return p


def board(args):
    ats, company, slug = args
    try:
        d = get(URLS[ats].format(slug))
        jobs = d if isinstance(d, list) else d.get("jobs", [])
        return company, [normalize(ats, company, j) for j in jobs], None
    except Exception as e:
        return company, [], f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/postings.jsonl")
    a = ap.parse_args()

    boards = json.loads((HERE / "boards.json").read_text())
    work = [(ats, name, slug) for ats, m in boards.items() if ats in URLS for name, slug in m.items()]
    total, kept, failed = 0, [], []
    with ThreadPoolExecutor(12) as ex:
        for company, jobs, err in ex.map(board, work):
            if err:
                failed.append(f"{company}: {err}")
                continue
            total += len(jobs)
            kept += [facts(j) for j in jobs if j["url"] and MAYBE_PRODUCT.search(j["title"])]

    seen, out = set(), []
    for p in kept:                       # the same req is sometimes posted twice under one URL
        if p["url"] not in seen:
            seen.add(p["url"])
            p["id"] = hashlib.sha1(p["url"].encode()).hexdigest()[:10]   # stable across fetches, so labels survive
            out.append(p)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        for p in out:
            f.write(json.dumps(p) + "\n")
    print(f"{len(work) - len(failed)}/{len(work)} boards · {total:,} open roles · "
          f"{len(out):,} kept by the title filter → {a.out}")
    for e in failed:
        print(f"  failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
