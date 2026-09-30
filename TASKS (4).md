# TASKS.md

Work top to bottom. Finish each phase's check before starting the next.
Log results in `RESULTS.md`. Verify anything marked `TO VERIFY` from the docs and files.

## Phase 0: Setup

- [x] Join the Playground competition and accept the rules
- [x] Create Kaggle API token (keep it only in `~/.kaggle/access_token`; never in the repo)
- [x] Download the competition zip into the project folder
- [x] Use WSL for local Linux-engine validation
- [x] Confirm existing Git repository at workspace root (folder name is `Pokemon`, not `ptcg-agent`)
- [x] Add `.gitignore` (data/, runs/, checkpoints, *.tar.gz, token files)
- [ ] Copy `CLAUDE.md` (project brief), `REQUIREMENTS.md`, `DESIGN.md`, `TASKS.md` into the repo
- [x] Install `kaggle` CLI (2.2.4)
- [ ] Revoke the token exposed in chat, configure a replacement locally, and run `kaggle competitions list`

**Check:** CLI works without the token appearing in any repo file.

## Phase 1: Understand the engine

- [x] List and extract the competition files (zip already downloaded; or use
      `kagglehub.competition_download('the-pokemon-company-ptcg-ai-battle-challenge-playground')`)
- [x] Read the cabt docs and the sample submission
- [ ] Read the public "Q Learning Baseline" notebook for structure only
- [x] Write `NOTES.md`: how to create a local game, observation format, options and
      actions, `deck.csv` format, best-of-three mechanics, time limits, rule differences,
      engine binary architecture
- [x] Run local random-agent games and save arena results

**Check:** a full local game runs end to end; every `TO VERIFY` item in the docs is
resolved or listed as still unknown in `NOTES.md`.

## Phase 2: Arena harness

- [x] `tools/arena.py`: parallel best-of-three, alternating first player, CSV output,
      win rate with 95% CI, crash and timeout handling
- [x] Benchmark mode: games per hour per core
- [x] Test random vs random; record throughput in `RESULTS.md`

**Check:** you have a games/hour/core number written down.

## Phase 3: Baseline and first submission

- [x] Heuristic baseline develops before attacking and attacks rather than passing, with legal-choice fallback
- [x] Baseline beats random in the arena with a clear margin
- [x] `tools/package.py`: build `submission.tar.gz` (`main.py` at top level), check size
      and structure, play one local game
- [ ] Submit via `kaggle competitions submit` or the website; confirm validation passes
- [ ] Record ladder rank in `RESULTS.md` (blocked until submission)

**Check:** baseline submission is on the ladder without an Error.

## Gate A: throughput decision

- Throughput decent (tens of thousands of games per day on available cores): go to Phase 4.
- Throughput very low: profile and optimize the harness first; do not spend on compute yet.

## Phase 4: Decks

- [x] `tools/deck_check.py` validating decks against the competition rules
- [x] Add the verified sample deck to `decks/`; additional candidates are still needed
- [x] `tools/roundrobin.py`: win-rate matrix with the baseline's play logic
- [ ] Rank decks, note counters, pick top candidates

**Check:** a ranked deck list with enough games per pair to see clear differences.

## Phase 5: Reuse survey

- [x] Read `ymgaq/ptcg-population-rl`: license, engine version, what can be reused
- [ ] Read `KleinHoumani/ptcg-selfplay-agent` and `squidistaken/pokemon-tcg-ai`
- [x] Write a short plan of small steps to a first policy that beats the baseline

**Check:** written plan; no RL pipeline code changed yet.

## Phase 6: Learning pipeline

- [ ] Tiny training run end to end (small model, few games)
- [ ] Exported policy loads inside an agent folder and passes the packaging check
- [ ] Policy beats the baseline in the arena (CI above 50%)
- [ ] Scale up in stages: more games, longer training, opponent pool
- [ ] Re-run deck round-robin with the learned policy

**Gate B (after first free-tier training week):** does the learned agent clearly beat
the baseline? If not, diagnose before spending credits.

**Gate C (before paid compute):** ladder rank versus effort. Decide whether more compute
would close the gap to the top. Set a hard spending cap first.

## Phase 7: Weekly loop

Each week:
1. Arena: new candidate vs current best.
2. Log in `RESULTS.md`.
3. Submit only arena winners.
4. Keep the two best candidates as the active submissions.

## Phase 8: Final stretch (from about Dec 20)

- [ ] Freeze the architecture; only low-risk improvements
- [ ] Test the final candidates for time and memory under the runtime limits
- [ ] Leave at least one full day of buffer before Jan 8, 2027 (deadline 11:59 PM UTC)
- [ ] Make sure the two active submissions are the two strongest and stable ones

## Key dates

| Date | Event |
|---|---|
| Sep 29, 2026 | Competition start |
| Jan 1, 2027 | Entry and team merger deadline |
| Jan 8, 2027 | Final submission deadline (11:59 PM UTC) |
| Jan 22, 2027 | Post-deadline evaluation ends |
