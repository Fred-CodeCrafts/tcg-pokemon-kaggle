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