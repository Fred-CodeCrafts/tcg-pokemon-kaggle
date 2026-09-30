# DESIGN.md

Design for `ptcg-agent`. Anything marked `TO VERIFY` must be confirmed from the cabt
docs, sample submission, or competition files before implementation.

## 1. Approach

Two tracks that share one evaluation harness:

1. **Development harness** (LLM coding agent): writes and maintains the arena, tools,
   and experiment code; analyzes replays; drafts heuristics. Runs only in development.
2. **Submitted agent**: a small CPU-only policy (heuristic first, then a small
   Transformer trained with PPO self-play). No network or LLM calls at inference.

Winning entries in the earlier Featured competition shared these traits: small
Transformers trained with self-play PPO, deck choice treated as half the problem,
a local arena for checkpoint selection, and specialists or matchup switching.

## 2. Repo layout (proposed)

```
ptcg-agent/
  CLAUDE.md           # project brief and rules for the coding agent
  REQUIREMENTS.md
  DESIGN.md
  TASKS.md
  NOTES.md            # verified engine facts (created in Phase 1)
  RESULTS.md          # experiment and submission log
  .gitignore          # competition data, checkpoints, tokens, submission archives
  data/               # downloaded competition files (not committed)
  decks/              # candidate deck.csv files
  agents/
    random/           # main.py + deck.csv
    baseline/         # heuristic agent
    <candidate>/      # each candidate agent folder is submittable as-is
  tools/
    arena.py          # parallel best-of-three matches, CSV output, CI
    package.py        # build and check submission.tar.gz
    deck_check.py     # validate deck.csv
    roundrobin.py     # deck win-rate matrix
  train/              # self-play RL pipeline (Phase 6)
  runs/               # logs, results CSVs, checkpoints (not committed)
```

## 3. Components

### 3.1 Agent interface (TO VERIFY)

Each turn the engine gives the agent an observation (game logs, board state, legal
options) and expects a list of chosen option indices. The engine only presents legal
moves. Confirm from the docs and sample: function name and signature in `main.py`,
observation fields, how multi-select choices are returned, and how the deck is loaded
from `deck.csv`.

Safety wrapper (all agents): wrap decision code in try/except and a time guard;
on any failure return a known-legal fallback choice. The agent must never raise.

### 3.2 Arena (`tools/arena.py`)

- Input: two agent folders, number of matches, worker count, seed.
- Runs best-of-three matches in parallel processes, alternating who goes first.
- Output CSV: match id, winner, game scores, turns, duration, errors, seeds.
- Prints win rate with a 95% confidence interval (Wilson interval on match results).
- Handles agent crashes and timeouts without stopping the run; counts them as errors.
- Benchmark mode: games per hour per core.

### 3.3 Packaging (`tools/package.py`)

Builds `submission.tar.gz` from an agent folder with `main.py` at the top level, checks
size below 197.7 MiB, verifies imports work when files live at
`/kaggle_simulations/agent/`, and plays one local game before finishing.

### 3.4 Decks

`deck_check.py` validates against the competition's deck rules (TO VERIFY). `roundrobin.py`
runs every deck pair with a fixed play policy and outputs a win-rate matrix. Deck
choice is made from this matrix, then re-checked once a learned policy exists.

### 3.5 Learned agent (Phase 6)

- Model: small Transformer over board-state tokens, about 1M to 2M parameters, CPU
  inference only. Set-style encoders are an option for hand and bench cards.
- Training: PPO self-play, optionally warm-started by imitating the heuristic baseline,
  then trained against a pool of past checkpoints and baselines (population).
- Reuse: adapt an open-source pipeline after checking license and engine compatibility.
- Selection: candidates only advance if they beat the current best in the arena with
  a confidence interval above 50%.

## 4. Experiment protocol

1. Change one thing at a time.
2. Evaluate in the arena versus the current best and versus the baseline.
3. Record in `RESULTS.md`: date, change, opponent, matches, win rate, CI.
4. Submit only agents that win in the arena.
5. Keep the two active submissions as the two best candidates.

Ladder rank is noisy early (uncertainty starts high), so trust the arena for decisions
and use the ladder as a sanity check.

## 5. Compute plan

- Local machine: development, arena, small runs.
- Kaggle notebooks (GPU, weekly quota): model training.
- New-account cloud credits: big CPU machine for bursts of self-play.
- Check the engine binary's CPU architecture (x86 vs ARM) before choosing machines.
- Spend in stages with go/no-go gates (see TASKS.md).

## 6. Risks

| Risk | Mitigation |
|---|---|
| Engine or rule differences from Featured code | Read forums; verify with small tests before reuse |
| Timeouts or crashes on the ladder | Safety wrapper and fallback; package check on target-like limits |
| Low self-play throughput | Measure early; profile before spending on compute |
| Stronger field joins later | Staged spend; keep a solid mid-rank as an acceptable outcome |
| Overfitting to one deck or opponent | Population training, round-robin re-checks |
| Secrets leaking | Token only in `~/.kaggle/access_token`; nothing in the repo |
