# AI PM Job Radar

Which open product roles at AI and tech companies are real product management jobs, and which of those are AI product jobs? A title filter can't tell you. This project asks a decision model instead, then measures whether that was worth it.

It scans public job boards at 31 companies, uses code for everything code is good at, and sends only the judgment calls to [Jev](https://docs.typesafe.ai), a model that answers typed multiple-choice questions with a confidence score instead of writing text.

## The problem

Keyword filters fail in both directions. On the first scan (2026-09-28), 7,332 open roles came back and 658 had "product," "PM," or "GM" in the title. Among them:

- **"Account Executive, Product Sales"** and **"Strategic Finance Manager, Product"** pass a title filter. Neither is a PM role.
- **"Business Systems Analyst, New Product Introduction"** passes too.
- A PM on a billing page at an AI company is not an AI PM. A PM whose title says "Platform" might be building the model API.

Whether a role is AI product work lives in the description, not the title.

## How it works

```
31 job boards ──► fetch.py ──► 7,332 roles
                   │  code: title contains product / PM / GM?     (stage 1: cheap, loose)
                   │  code: pay range, remote flag, dedupe         (facts, not judgment)
                   ▼
                 658 postings ──► Jev: 3 questions per posting     (stage 2: meaning)
                                   │  role       pm / adjacent / not_pm / unclear
                                   │  ai_focus   ai_product / ai_feature / not_ai / unclear
                                   │  ml_background   yes/no probability
                                   ▼
                                 buckets, with a confidence floor per question
                                 anything under its floor goes to review
```

**Code computes facts, the model judges meaning.** Pay ranges, dates, and deduplication are arithmetic and string matching, which models are bad at and code gets right every time. Jev only gets questions that need reading comprehension.

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

*Pending the first labeled run. Every number here will come from [`eval/results.md`](eval/results.md), and none will be estimated.*

| | Jev | Title regex |
|---|---|---|
| `role` agrees with hand labels | | |
| `ai_focus` agrees with hand labels | | |
| Cost, full run | | $0 |
| Time, full run | | |

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

To scan different companies, edit [`radar/boards.json`](radar/boards.json). Any company on Greenhouse, Ashby, or Lever works.

## Credits

The question-design approach draws on Aakash Gupta's [how-to-jev](https://www.product-growth.com) skill (MIT). The code is written from scratch for this project.
