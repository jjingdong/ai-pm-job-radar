# Eval: 40 hand-labeled postings

## The two decisions

| Decision | Jev | Title regex | Scored on |
|---|---|---|---|
| Is it a PM role? | 40/40 (100%) | 39/40 (98%) | all labeled postings |
| Is it AI product work? | 15/15 (100%) | 5/15 (33%) | labeled PM roles with a definite AI label (3 labeled unclear left out) |

### Regex wrong: is it a PM role? (1)

- Brex · Director of Product, Growth/AI (label: pm, said: not_pm)

### Regex wrong: is it AI product work? (10)

- Anthropic · Product Manager, Safeguards (Generalist) (label: ai_product, said: not_ai)
- Datadog · Product Management Intern (label: ai_product, said: not_ai)
- Pinterest · Product Manager II, Search Experience (label: ai_product, said: not_ai)
- Scale AI · Staff Technical Product Manager (label: ai_product, said: not_ai)
- Stripe · Staff Product Manager, Connect (label: ai_product, said: not_ai)
- Stripe · Product Manager, Employee Experiences (label: ai_product, said: not_ai)
- Figma · Manager, Product Management - Roundtripping (label: ai_product, said: not_ai)
- Vercel · Product Manager, Dashboard (label: ai_product, said: not_ai)
- Coinbase · Group Product Manager, Money Movement (label: ai_product, said: not_ai)
- Cloudflare · Senior Product Manager, Email Security (label: ai_product, said: not_ai)

### Jev wrong: is it a PM role? (0)

None.

### Jev wrong: is it AI product work? (0)

None.

## Strict agreement, every label as written

- `role` (pm / adjacent / not_pm / unclear): Jev 20/40 (50%). Most misses are Jev saying `adjacent` where the label says `not_pm`; both mean not a PM role.
- `ai_focus` (ai_product / ai_feature / not_ai / unclear): Jev 9/18 (50%) on labeled PM roles.

| Company | Title | Label | Jev | conf |
|---|---|---|---|---|
| Stripe | Product Manager - Issuance, Bridge | unclear | not_ai | 1.0 |
| Robinhood | Staff Product Manager, Banking | unclear | not_ai | 1.0 |
| Coinbase | Group Product Manager, Money Movement | ai_product | ai_feature | 0.99 |
| Vercel | Product Manager, Dashboard | ai_product | ai_feature | 0.85 |
| Airbnb | Product Manager, Pricing | unclear | not_ai | 0.81 |
| Cloudflare | Senior Product Manager, Email Security | ai_product | ai_feature | 0.72 |
| Brex | Director of Product, Growth/AI | ai_product | ai_feature | 0.6 |
| Stripe | Staff Product Manager, Connect | ai_product | ai_feature | 0.5 |
| Datadog | Product Management Intern | ai_product | ai_feature | 0.33 |

`ml_background` at a 0.5 cut: 17/18 (94%) agree. 0 of 18 labeled PM roles need hands-on ML, so this is only a test of false alarms.

