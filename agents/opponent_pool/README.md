# Opponent Pool

This pool is for local evaluation, not direct submission.

| Agent | Purpose |
|---|---|
| `random` | Smoke-test floor only; excluded from promotion decisions |
| `baseline` | Current submitted heuristic and sample deck |
| `ymgaq_abomasnow` | Public Apache-2.0 rule policy with its bundled deck |
| `baseline_policy_ymgaq_deck` | Deck-only control: current baseline policy with the ymgaq deck |

Compare candidates against this pool with paired seat assignments. Keep random for crash and legality checks, but use the non-random pool for promotion decisions.
