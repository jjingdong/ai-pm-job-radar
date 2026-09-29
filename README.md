# AI PM Job Radar

Which open product roles at AI and tech companies are real product management jobs, and which of those are AI product jobs? A title filter can't tell you. This project asks a decision model instead, then measures whether that was worth it.

It scans public job boards at 31 companies, uses code for everything code is good at, and sends only the judgment calls to [Jev](https://docs.typesafe.ai), a model that answers typed multiple-choice questions with a confidence score instead of writing text.

## The problem

A scan on 2026-09-29 returned 7,301 open roles, and 658 had "product," "PM," or "GM" in the title. Those 658 include:

- **17 "Account Executive, Product Sales" roles at Stripe**, plus "Strategic Finance Manager, Product" and "Business Systems Analyst, New Product Introduction." None of these are PM roles.
- **PM roles whose titles never mention AI**, like "Staff Product Manager, Connect" or "Senior Product Manager, Email Security," where the description makes AI central to the job.

A title filter can mostly handle the first problem. It can't handle the second, because whether a role is AI product work lives in the description, not the title.

## How it works

```
31 job boards ──► fetch.py ──► 7,301 roles
                   │  code: title contains product / PM / GM?     (stage 1: cheap, loose)   → 658
                   │  code: merge one job posted in several cities                           → 571
                   │  code: pay range, remote flag                 (facts, not judgment)
                   ▼
                 571 postings ──► Jev: 3 questions per posting     (stage 2: meaning)
                                   │  role       pm / adjacent / not_pm / unclear
                                   │  ai_focus   ai_product / ai_feature / not_ai / unclear
                                   │  ml_background   yes/no probability
                                   ▼
                                 buckets, with a confidence floor per question
                                 anything under its floor goes to review
```

**Code computes facts, the model judges meaning.** Pay ranges, dates, and deduplication are arithmetic and string matching, which models are bad at and code gets right every time. Jev only gets questions that need reading comprehension. Deduplication alone removed 13% of postings, the same job listed once per city, before any model saw them.

**Every question has an escape option.** `unclear` is always available, and the instructions say when to use it. A model forced to pick between two wrong answers still picks one, confidently.

**One judgment per question.** "Is this an AI PM role?" is two questions: is it PM work, and is the product AI. Combining them happens in the bucket rules, where the logic is visible and testable.

**Floors are per question and measured, not guessed.** They start at 0.7 for `role` and 0.6 for `ai_focus`, and move based on where the wrong answers cluster in the eval.

All questions, floors, and bucket rules live in [`radar/spec.json`](radar/spec.json). Changing behavior means editing that file, not the code.

## Evaluation

The question isn't "is Jev accurate." It's "is Jev better than the rule it replaces, by enough to justify the call."

1. A fixed random sample of 40 postings is labeled by hand, reading the full description, before looking at any model output ([`eval/label.py`](eval/label.py)).
2. Jev and a title regex ([`radar/baseline.py`](radar/baseline.py)) both answer the same postings.
3. [`eval/score.py`](eval/score.py) reports agreement with the hand labels for each, and lists every posting Jev got wrong with the confidence it gave. Wrong answers at high confidence mean the question needs rewriting; wrong answers at low confidence mean the floor is doing its job.

### Results

Measured on 2026-09-29 with `jev-1.13.0`. Full detail in [`eval/results.md`](eval/results.md).

| | Jev | Title regex |
|---|---|---|
| Is it a PM role? (40 labeled postings) | **40/40** | 39/40 |
| Is it AI product work? (15 labeled PM roles) | **15/15** | 5/15 |
| Full run, 571 postings | 20.6 s · $0.046 | instant · $0 |
| Median latency per posting | 278 ms | n/a |

**What this says:**

- **For "is it a PM role," the regex nearly ties.** Titles are good at that question. The regex's one miss was "Director of Product, Growth/AI." If that were the only question, the model wouldn't be worth adding.
- **For "is it AI work," the regex misses two in three.** It called 10 of the 15 AI roles non-AI, because their titles never mention AI. Jev read the descriptions and got all 15. This is the question the model is worth paying for, at under five cents a run.
- **The review bucket is the cost of the floors.** On the full run, 82 of 571 postings (14%) landed in review: 52 where the `role` answer came in under its 0.7 floor, and 30 PM roles where `ai_focus` came in under 0.6 or was `unclear`. Nothing in the labeled sample shows those floors are too strict or too loose yet. That needs labels drawn from the review bucket itself.

**Limits, stated plainly:**

- **40 labels is a small sample.** 15/15 is not "100% accurate." It means no errors in 15 tries, which is consistent with a real error rate of up to about 20%. The next step is more labels, weighted toward the review bucket.
- **The finer AI question is less settled.** On the three-way split (`ai_product` / `ai_feature` / `not_ai`), Jev and the labels agree on 9 of 18. The labels put every AI-involved role in `ai_product`; Jev put 6 of them in `ai_feature`. That's a definition problem, not a model problem, and it's the next change to the spec.
- **Three labels were corrected after review.** They were key slips (a designer, a program manager, and an account executive marked "PM" by mistake), caught because they contradicted the notes on similar postings. Each correction is marked in [`eval/labels.csv`](eval/labels.csv).
- **The model version is pinned in the results.** Scores are for `jev-1.13.0`. A newer version needs a rerun of the same 40 before the numbers carry over.

## Run it

Python 3.9+, standard library only.

```bash
python3 radar/fetch.py                     # pull every board, keep possible product roles
python3 radar/run.py --dry-run             # token and cost estimate, no calls
python3 radar/run.py --sample 40           # review a sample before running everything
python3 radar/run.py                       # everything; results cached, reruns are free
```

Jev is called through TypeSafe's API directly if `TYPESAFE_API_KEY` is set, otherwise through [Vercel AI Gateway](https://vercel.com/docs/ai-gateway/sdks-and-apis/typesafe) with `AI_GATEWAY_API_KEY`. Either key can live in your environment or in `~/.config/typesafe/.env` / `~/.config/ai-gateway/.env`, never in the repo. Output lands in `output/summary.md` and `output/results.csv`.

To reproduce the eval: `python3 eval/label.py`, then `python3 radar/run.py --ids eval/labels.csv`, then `python3 eval/score.py`.

To scan different companies, edit [`radar/boards.json`](radar/boards.json), or put your own list in `radar/boards.local.json` (gitignored, used automatically when present). Any company on Greenhouse, Ashby, Lever, or Workable works.

## Credits

The question-design approach draws on Aakash Gupta's [how-to-jev](https://www.product-growth.com) skill (MIT). The code is written from scratch for this project.
