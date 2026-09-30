# REQUIREMENTS.md

Project: `ptcg-agent`, an agent for the Kaggle competition
"The Pokémon Company - PTCG AI Battle Challenge Playground".

## 1. Goal

Build the strongest agent we can for the Playground ladder (best-of-three format)
before the final submission deadline of **Jan 8, 2027** (entry and team merger
deadline Jan 1, 2027; games keep running about two weeks after; final ranking by
a Bradley-Terry tournament).

Stretch goal: finish in the top 5 (prizes are merchandise only, no medals or points).
Minimum goal: a working, stable agent that beats simple baselines.

## 2. Rules for the coding agent (read first)

- Never guess API details. Read the cabt docs (https://matsuoinstitute.github.io/cabt/),
  the sample submission, and the competition files in the downloaded zip first.
- Anything marked `TO VERIFY` in these docs must be confirmed from those sources
  and written into `NOTES.md` before it is relied on.
- Work in small steps. After each step, say what you verified and how.
- Keep `RESULTS.md` up to date: date, what changed, measured win rate, sample size,
  confidence interval.
- Never write secrets (Kaggle token) into the repo, docs, logs, or commit history.
- Do not commit competition data (the zip or extracted files). Add them to `.gitignore`.

## 3. Competition constraints (from the competition page)

| Item | Value |
|---|---|
| Submission format | `.tar.gz` with `main.py` at the top level (not nested) plus `deck.csv` |
| Create with | `tar -czvf submission.tar.gz *` (run inside the agent folder) |
| Agent files at runtime | `/kaggle_simulations/agent/` (imports must work from there) |
| Max size | 197.7 MiB |
| Runtime resources | 2 vCPUs, 12.2 GiB RAM, 11.8 GiB disk |
| Daily submissions | 5 |
| Active submissions | latest 2 only |
| Validation | first game is the submission vs a copy of itself; failure marks it Error |
| Rating | Gaussian skill, starting mu = 600 |
| Engine | cabt (Pokémon TCG simulator for kaggle-environments) |
| Per-turn I/O | observation (logs, board state, legal options) in; indices of chosen options out |
| Rules differences | simulator differs from official rules in places; documented in forums (TO VERIFY) |

TO VERIFY: per-move and per-match time limits, whether the agent may use the network,
whether GPU is available at submission time (assume no), and the exact best-of-three
mechanics (deck reuse, sideboarding, who goes first in game 2 and 3).

## 4. Functional requirements

- FR1. Local arena that runs many best-of-three matches between two agent folders in
  parallel and reports win rate with a 95% confidence interval.
- FR2. Arena benchmark mode reporting games per hour per CPU core.
- FR3. Baseline agent that never returns an illegal choice and never crashes.
- FR4. Reproducible packaging: one command builds `submission.tar.gz` and checks the
  structure, size, and that it plays a full game locally.
- FR5. Deck validator that checks `deck.csv` against the competition's deck rules
  (TO VERIFY from the data page and card data).
- FR6. Deck round-robin tool producing a win-rate matrix.
- FR7. Learned agent (self-play RL) that beats the baseline in the arena with statistical
  significance, small enough to run within the resource limits.
- FR8. Results log with every experiment and submission.

## 5. Non-functional requirements

- NFR1. Agent must respect the time limits (TO VERIFY) with margin; fall back to a
  safe heuristic on any error or timeout.
- NFR2. Model and dependencies fit within 197.7 MiB and run on 2 vCPUs, so inference
  must be CPU-only and small (winners used roughly 1M to 2M parameter Transformers).
- NFR3. All experiments seeded and logged so results can be reproduced.
- NFR4. Compute budget is staged (see TASKS.md gates). Free tiers first.

## 6. Out of scope (for now)

- LLM calls inside the submitted agent.
- Hackathon-track report (only the Playground ladder).

## 7. Reference material

- Public notebook "Q Learning Baseline" for this Playground (public score 553.4,
  Apache 2.0). Treat as one data point on how a sample agent is structured. Read it
  before writing our baseline. Do not assume its score is a good target.
- Open-source solutions from the earlier Featured competition (check licenses and
  engine-version compatibility before reusing anything):
  - `ymgaq/ptcg-population-rl`
  - `KleinHoumani/ptcg-selfplay-agent`
  - `squidistaken/pokemon-tcg-ai`

## 8. Open questions

- Exact rule differences between the Playground engine and the Featured one.
- Whether decklists are restricted to a provided card pool.
- Real games/hour/core on our machine (measured in TASKS.md, Phase 2).
