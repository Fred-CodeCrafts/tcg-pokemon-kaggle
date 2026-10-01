# Verified Engine Notes

## Agent Contract

- The sample defines `agent(obs_dict) -> list[int]` in `main.py`.
- For an action, the list must contain unique option indexes in range, with length between `select.minCount` and `select.maxCount`.
- `select` and `current` are `None` during the initial deck-selection phase; the sample reads 60 integer IDs from `deck.csv` in that phase.
- The observation includes `logs`, `current`, and `select`. `current.yourIndex` identifies the acting player. Select contexts and option types are numeric enums in the sample API.
- The baseline includes an embedded legal 60-card sample-deck fallback if all runtime `deck.csv` paths are unavailable; a regression test simulates that startup condition. This addresses the reported empty-deck failure mode, though the exact previously uploaded artifact was not available for forensic comparison.
- The bundled sample plus cabt docs were read. A local native-engine random game completed successfully: 25 selections and 7 turns.
- The public Q Learning Baseline page exposed its description, public score, and Apache-2.0 label, but not its executable notebook cells in this environment. No code from that notebook was relied on.

## Local Engine and Decks

- cabt docs show `battle_start(deck0, deck1)`, `battle_select(indices)`, and `battle_finish()`; the bundled Python wrapper loads the platform's native library.
- `BattleStartReverse` yields an initial selection with `context == 41` (`IS_FIRST`), one Yes option (`type == 1`) and one No option (`type == 2`); the acting player is index 1. This was observed locally.
- The engine initializer checks 60 card IDs, known IDs, at least one Basic Pokémon, no more than four copies of the same card name except Basic Energy, and at most one ACE SPEC. These checks are in the supplied `Api.h`.
- English CSV `Card ID` values map to engine card IDs. Its stage field distinguishes Basic Pokémon and Basic Energy; `Rule` identifies ACE SPEC.
- The engine API seeds its game RNG internally using `std::random_device`; the local wrapper does not expose a seed. The arena seed controls Python agent randomness and match scheduling, not native game reproducibility.
- WSL Kali Linux 3.13 x86_64 successfully loaded the bundled `libcg.so`; the crash/timeout tests, benchmark, and baseline-vs-random evaluation all passed there.
- Kaggle CLI 2.2.4 is installed on Windows and authenticated; competition listing and submissions work through `python -m kaggle`.

## Kaggle Episode Retrieval

Use the Kaggle CLI to connect a submission to its public and validation episodes, then download the replay and per-agent logs. Keep each submission in its own folder so episodes from different deck versions are not mixed:

```powershell
$competition = "the-pokemon-company-ptcg-ai-battle-challenge-playground"
$submissionId = "<submission_id>"
$episodeId = "<episode_id>"
$resultPath = "real results\$submissionId"

New-Item -ItemType Directory -Force $resultPath
kaggle competitions submissions -c $competition --format json
kaggle competitions episodes $submissionId --format json
kaggle competitions replay $episodeId --path $resultPath
kaggle competitions logs $episodeId 0 --path $resultPath
kaggle competitions logs $episodeId 1 --path $resultPath
```

The replay contains the episode observations, actions, agents, and rewards. Logs use zero-based agent indexes; download both indexes first, then identify the submitted agent from the replay before interpreting its log. Check the replay's deck/action data before treating an episode as evidence about a particular deck. For example, `real results/115643067.json` is an Abomasnow mirror, not a Mawile match.

- Latest Abomasnow candidate for comparison: submission `56704387` ("Bundle cg runtime and validate extracted import") had a latest public episode at `115849071` on `2026-09-30T15:46:08.689000`. This gives the newest pointer to the Abomasnow rule-policy package used in the current ladder run.
- Latest baseline reference for later Excadrill work: submission `56700484` ("Validated baseline resubmission") had a latest public episode at `115820366` on `2026-09-30T14:30:23.724000`. Use this as the current ladder baseline datapoint alongside the recent Mawile analysis when checking whether a candidate deck is improving relative to the baseline.
- First expanded Mega threat screen: `decks/mega_charizard_y_excadrill_test.csv` uses Mega Charizard Y (`928`), Charmander (`926`), Charmeleon (`927`), Mega Signal (`1145`), Fire Energy (`2`), and generic search/draw cards. It passed deck validation with 60 legal cards. In 10 paired-seat smoke matches against the Prime Catcher Excadrill deck, it went 0-10 with 0 errors; this is exploratory because both sides used the generic policy.
- Next expanded Mega threat screen: `decks/mega_gardevoir_excadrill_test.csv` uses Mega Gardevoir (`747`), Ralts (`745`), Kirlia (`746`), Mega Signal (`1145`), Psychic Energy (`5`), and generic search/draw cards. It passed deck validation with 60 legal cards. In 10 paired-seat smoke matches against the Prime Catcher Excadrill deck, it went 0-10 with 0 errors and 22 games; this is exploratory and not a conclusive matchup result.
- Excadrill Abomasnow tuning note: a narrow experiment that prioritized Boss/Prime Catcher on Benched Snover went 40% in 20 matches (49 games), while the reverted control recheck went 45% in 20 matches (50 games). The change was removed; the result is small and noisy, but it provides no positive evidence for early Snover gusting.
- Historical replay matching: `tools/replay_deck_audit.py` now extracts the two 60-card deck actions from a Kaggle replay and compares them with local files. Replay `115853600` is Abomasnow agent 0 versus Mawile agent 1; `decks/abomasnow_episode_115853600.csv` and `agents/mega_mawile_counter/deck.csv` match both replay decks exactly. A 10-match local smoke with the exact pair went 20% Abomasnow / 80% Mawile with 0 errors, matching the archived episode's winner direction but not expected to reproduce its exact games.
- Simulation parity boundary: the bundled engine reports module version `1.32.7`, and the local wrapper matches the observed BO3 first-player order for replay `115853600` (game 1 first player 0, game 2 first player 1). Exact outcomes cannot be replayed because the native game RNG is seeded internally with `random_device`; local `random.seed()` only controls Python policy randomness. Kaggle also allows 10,000,000 episode steps and 2,000 seconds runtime, while local arena safety limits are 10,000 decisions per game and 120 seconds per match.
- Pool-wide Excadrill decision: with the same specialized Excadrill policy, Metal-engine deck `decks/mega_excadrill_metal_engine.csv` scored 245/300 (81.7%, 0 errors) across the six non-random pool opponents. Prime Catcher scored 232/299 resolved (77.6%, one engine-result error). Metal is the current pool-wide candidate, but its current Abomasnow confirmation was only 42%, so it is not a solved matchup and should not be judged from aggregate rate alone.
- Prime Catcher pilot update: the active Excadrill pilot now penalizes `Undermine` by 120 points while Mega Excadrill has fewer than five attached Energy, preserving setup for the 330-damage `Maximum Drilling` threshold. In an isolated 50-match test this pilot reached 52% versus Abomasnow; after promotion, the active directory reached 58% (119 games, 0 errors). The same pilot remained strong in 30-match screens versus baseline (83.3%), deck-only control (86.7%), and both Dragapult variants (100% each), with Mega Lucario at 56.7%.
- Opponent-aware pilot experiment: an isolated version added threat bonuses for Mega Abomasnow, Mega Lucario, and Dragapult, plus a stronger five-Energy Maximum Drilling preference. It went 46% vs Abomasnow in 50 matches with 0 errors, below the active pilot's 58% screen, so it was rejected and never promoted.
- Submission follow-up (2026-10-01): submission `56741709` used the Prime Catcher specialist description but later became `ERROR`; its local package smoke did not guarantee Kaggle startup compatibility. Submission `56742422` completed successfully after fixing deck lookup when `__file__` is unavailable, with public score `482.4` and latest public episode `116121082`. Judge `56742422` as the current successful ladder result, not the failed `56741709` upload.
- One-at-a-time Trainer/Item testing: replacing Prime Catcher with Precious Trolley reached 60% vs Abomasnow in 50 matches, but its 30-match Mega Lucario screen was 46.7%, so it remains an unpromoted candidate. Replacing one Carmine with a third Boss's Orders reached 46.7% vs Abomasnow; replacing one Poké Pad with a second Switch reached 36.7%. Both ordinary-card swaps were rejected; the active Prime Catcher list remains unchanged.
- ACE comparison: the current opponent pool uses Maximum Belt (baseline), Precious Trolley (Abomasnow), Prime Catcher (Dragapult), and Hero's Cape (Mega Lucario). One-variable Excadrill screens versus Abomasnow measured Precious Trolley 60%, Prime Catcher 58%, Secret Box 52%, Maximum Belt 52%, and Hero's Cape 52%. Secret Box searches an Item, Tool, Supporter, and Stadium but the current Excadrill list has no Tool/Stadium; Maximum Belt and Hero's Cape also need explicit Tool-priority logic for a fully fair test. No ACE replacement is promoted; Prime Catcher remains active.
- Fair ACE pilot comparison: `agents/mega_excadrill_generic_ace/main.py` scores ACE effects from runtime text rather than naming Prime Catcher. Across 120 matches per ACE and the six non-random pool opponents, Prime Catcher went 97/120 (80.8%), Precious Trolley 96/120 (80.0%), and Secret Box 99/120 (82.5%), all with 0 errors. Abomasnow slices were Prime 40%, Trolley 40%, Secret 45%; the generic pilot comparison does not justify replacing the active specialized Prime Catcher pilot, which recently reached 58% vs Abomasnow.

## Arena Assumptions and Unknowns

- The local arena's BO3 protocol is three independent games with the same two decks, stopping when a player wins two. It alternates the forced first player A/B/A within a match and reverses the opening seat in the next match. This is a declared local evaluation convention, not yet verified as identical to Kaggle's official BO3 progression.
- Official sideboarding/deck reuse, exact game 2/3 starting-player policy, per-move/per-match deadlines, runtime network/GPU rules, and simulator rule differences remain unverified from available documentation. Confirm these on the competition's evaluation docs/discussion before treating local BO3 rates as ladder-equivalent.
- The local run used Windows x64 and the bundled `cg.dll`. Kaggle's target runtime is Linux; package smoke tests use the supplied local engine and do not establish Kaggle-side compatibility or timing.

## Learning Pipeline Survey

- `ymgaq/ptcg-population-rl` is Apache-2.0 and targets the earlier Featured `pokemon-tcg-ai-battle` competition. Its README describes four fixed-deck pipelines: C++ rule teachers, LightGBM ranking, Transformer distillation, PPO, and C++ inference; the model listed is 980,916 parameters.
- Reusable concepts: record observations/actions/rewards, learn a candidate-ranking policy, distill into a compact pointer Transformer, use PPO/GAE, and evaluate with swapped seats and fixed opponent pools.
- Adaptation required: deck/card vocabulary and features, the playground observation/action schema, local arena bridge, inference packaging, and exact engine/API parity. The README's engine is external and excluded from its Git repository; it does not establish version identity with this Playground's cabt package.
- Main risks: Featured-vs-Playground card/engine differences, unavailable build assets, C++ ABI or API mismatches, and costly feature reimplementation. No code has been copied or adapted from that repository.

### Small-Step Training Plan

1. Compare the source observation/action structures against the Playground sample and establish exact feature/action parity before reusing feature code.
2. Record a small set of baseline-vs-baseline games as observation/action/reward examples and verify replayed decisions remain legal.
3. Adapt the rule-policy teacher and train a tiny action-ranking model on those records; compare it with the heuristic in the local arena.
4. Distill the ranking policy into a CPU-sized pointer Transformer and verify its packaged agent completes local games.
5. Add short PPO updates with a small opponent pool only after the exported policy beats the baseline in arena matches with a 95% CI above 50%.
6. Increase rollout volume and pool size in stages, logging each result; stop to profile if arena throughput or inference time becomes a bottleneck.

## Public Reuse Audit (2026-09-30)

- `ymgaq/ptcg-population-rl`: Apache-2.0. Targets the earlier `pokemon-tcg-ai-battle` competition. The repository does not state cabt `1.32.7`; it downloads the competition engine separately. It includes official rule-agent code and 60-card decks, including `mega_abomasnow/deck.csv`, but trained weights and build artifacts are excluded. Its Mega Abomasnow rule agent was cloned and completed a local BO3 against the random agent with 0 errors.
- `KleinHoumani/ptcg-selfplay-agent`: MIT. Also targets the earlier competition and uses the cabt SDK, but no explicit cabt version `1.32.7` is declared. It includes Dragapult and Sylveon decklists and deployment/training code; the required `ppo.pt`, specialist weights, card data, embeddings, and deck pools are not in the Git tree.
- `squidistaken/pokemon-tcg-ai`: MIT. Targets the earlier competition and uses the cabt SDK, but no explicit cabt version `1.32.7` is declared. It includes an example deck and submission/runtime code; the tracked checkpoint directory contains configuration only, not a trained model weight file. Deck corpora are fetched from public GitHub releases.
- Competition rules permit publicly available external data, models, and tools when reasonably accessible and rights-cleared. Open-source code used in a submission must use an OSI-approved license with no commercial-use restriction; all three listed licenses meet that requirement. The rules prohibit network ingress/egress during evaluation, restrict Competition Data to competition use, and require rights clearance for external data/models. Public code sharing during the competition must occur on the competition's Kaggle forum/notebooks; these rules do not automatically grant rights to bundled Pokémon elements or competition data.
- Engine compatibility is not proven for any repository: all three target an earlier competition and do not pin cabt `1.32.7`. Reusing the `ymgaq` rule policy is currently the lowest-risk path; reusing either PPO agent requires a substantial asset and compatibility port.