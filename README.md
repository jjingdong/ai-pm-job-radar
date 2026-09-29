# AI PM Job Radar

I built this to test [Jev](https://docs.typesafe.ai), a decision model from TypeSafe. Jev doesn't write text. You give it a posting and a multiple-choice question, and it returns an answer with a confidence score in about 0.3 seconds, for a fraction of a cent. I wanted to find out whether it's accurate and cheap enough to replace the simple rules people use today.

I tested it on PM job listings, a problem I know well. Most job alerts filter on keywords in the title, so the question became: can Jev sort product management listings better than a keyword filter? Specifically, can it tell which roles are real PM jobs, and which of those are AI product jobs?

My guess going in was that titles work well enough for the first question but not for the second, because most AI PM roles don't have "AI" in the title. This project tests that guess on real listings from 31 AI and tech companies.

## The problem

A scan on 2026-09-29 returned 7,301 open roles. 658 had "product," "PM," or "GM" in the title, and many of those aren't PM jobs. Seventeen are "Account Executive, Product Sales" roles at Stripe, and others include "Strategic Finance Manager, Product" and "Business Systems Analyst, New Product Introduction."

Other roles have the opposite problem. "Staff Product Manager, Connect" and "Senior Product Manager, Email Security" read like ordinary PM roles, but their descriptions involve AI product work. A title filter only sees the title, so it misses them.

## How it works

```
31 job boards ──► fetch.py ──► 7,301 roles
                   │  title contains product / PM / GM?        → 658
                   │  merge the same job posted in several cities → 571
                   │  pay range, remote flag
                   ▼
                 571 postings ──► Jev, 3 questions per posting
                                   │  role            pm / adjacent / not_pm / unclear
                                   │  ai_focus        ai_product / ai_feature / not_ai / unclear
                                   │  ml_background   yes/no probability
                                   ▼
                                 buckets, with a confidence floor per question
                                 anything under its floor goes to review
```

The title filter runs first and is deliberately loose. A sales role that gets through costs a fraction of a cent to check, and Jev screens it out. A real PM role that the filter drops never reaches Jev at all.

Code handles pay ranges, remote flags, and duplicates, since those are exact matching and don't need a model. Merging duplicates removed 13% of postings before Jev saw any of them.

I split "is this an AI PM job?" into separate questions, so when an answer is wrong I can tell which part went wrong. Code combines the answers into buckets using rules that are easy to read and change.

Every question has an `unclear` option, so Jev isn't forced to pick between two wrong answers. Answers also have to clear a confidence floor (0.7 for `role`, 0.6 for `ai_focus`) or they go to a review bucket. I haven't tuned those floors yet.

All questions, floors, and bucket rules are in [`radar/spec.json`](radar/spec.json).

## Evaluation

I compared Jev against a title-only keyword rule ([`radar/baseline.py`](radar/baseline.py)), since that's what it would replace.

I labeled a random sample of 40 postings by reading each full description in [`eval/label.py`](eval/label.py), which doesn't show Jev's answers. Then [`eval/score.py`](eval/score.py) scored Jev and the keyword rule against my labels.

### Results

Measured on 2026-09-29 with `jev-1.13.0`. Every miss is listed in [`eval/results.md`](eval/results.md).

| | Jev | Title rule |
|---|---|---|
| Is it a PM role? (40 labeled postings) | 40/40 | 39/40 |
| Is it AI product work? (15 labeled PM roles) | 15/15 | 5/15 |
| Needs hands-on ML background? (18 labeled PM roles) | 17/18 | |
| Sent to review, full run | 82/571 (14%) | |
| Cost, full run of 571 postings | $0.046 | $0 |
| Time per posting, median (95th percentile) | 278 ms (374 ms) | instant |

My guess was right. On the PM question, the title rule nearly matched Jev, missing only "Director of Product, Growth/AI." On the AI question, the title rule missed 10 of 15 because their titles don't mention AI, and Jev missed none. Jev is only needed for the AI question, but I kept it on both because the cost comes almost entirely from reading the posting, and an extra question adds very little.

The ML background result only shows that Jev rarely flags ML when it isn't needed. None of the 18 labeled roles needed hands-on ML, so it doesn't show whether Jev can spot one that does. The AI result has the same gap in the other direction: none of the 18 were labeled not AI.

The full run cost about $0.08 per 1,000 postings and took 20.6 seconds with 12 calls in parallel. Confusion grids, token counts, and the full speed breakdown are in [`eval/details.md`](eval/details.md).

### What it found

Of 7,301 open roles at 31 companies, Jev sorted 95 into AI PM roles, 4 of them needing hands-on ML, and another 42 into PM roles on products adding AI features. That's 137 roles to read instead of 7,301. Another 82 went to review, and the other 352 were either not PM or PM roles without AI.

### Limits

Forty labels is a small sample. Even with 15 of 15 correct, the real error rate could be as high as about 20%.

Jev and I use different definitions of an AI product. I labeled every role that involves AI as `ai_product`, and Jev put 6 of them in `ai_feature`, meaning a regular product that's adding AI. The scores above count both as AI work, so this only affects the exact label, but I'd write a clearer definition before relying on that split.

I corrected three of my labels after review: a designer, a program manager, and an account executive that I had mistakenly marked as PM. Each contradicted my notes on nearly identical postings. I made these fixes after seeing Jev's answers, so I only corrected clear mistakes like these. Each one is marked in [`eval/labels.csv`](eval/labels.csv).

I'm the only person who labeled the data. A second person labeling the same 40 would show how reliable the labels are.

The scores are for `jev-1.13.0`. A newer version needs a rerun on the same 40 postings before these numbers apply to it.

### Next

1. Label the targeted batch in [`eval/targeted.csv`](eval/targeted.csv): 30 postings picked to cover what the random 40 couldn't, including PM roles Jev says aren't AI, roles that may need hands-on ML, and postings from the review bucket. [`eval/pick.py`](eval/pick.py) explains how they were chosen. Most were picked using Jev's own answers, so they're scored per group, not as one accuracy number.
2. Write a clearer definition of "AI product," then relabel and rerun.
3. Get a second person to label the same postings.
4. Check a sample of the titles the keyword filter rejected, to make sure real PM roles aren't dropped before Jev sees them.

## Run it

Python 3.9+, standard library only.

```bash
python3 radar/fetch.py                     # pull every board, keep possible product roles
python3 radar/run.py --dry-run             # token and cost estimate, no calls
python3 radar/run.py --sample 40           # review a sample before running everything
python3 radar/run.py                       # everything; results cached, reruns are free
```

The code calls Jev through TypeSafe's API if `TYPESAFE_API_KEY` is set, and through [Vercel AI Gateway](https://vercel.com/docs/ai-gateway/sdks-and-apis/typesafe) with `AI_GATEWAY_API_KEY` otherwise. Keep keys in your environment or in `~/.config/typesafe/.env` / `~/.config/ai-gateway/.env`, not in the repo. Output goes to `output/summary.md` and `output/results.csv`.

To reproduce the eval, run `python3 eval/label.py`, then `python3 radar/run.py --ids eval/labels.csv`, then `python3 eval/score.py`.

To label and score the targeted batch:

```bash
python3 eval/label.py --ids eval/targeted.csv --out eval/labels-targeted.csv
python3 radar/run.py --ids eval/labels-targeted.csv
python3 eval/score.py --labels eval/labels-targeted.csv --strata eval/targeted.csv --out eval/results-targeted.md
```

To scan other companies, edit [`radar/boards.json`](radar/boards.json), or put your own list in `radar/boards.local.json`, which is gitignored and used automatically when present. Any company on Greenhouse, Ashby, Lever, or Workable works.

## How this was built

I built this with [Claude Code](https://claude.com/claude-code), which wrote the code and drafted the questions. I set the direction, labeled the evaluation set, reviewed every result, and decided what to measure and report.

The approach to writing questions for Jev draws on Aakash Gupta's [how-to-jev](https://www.aibyaakash.com/p/jev-ai-model) skill (MIT).
