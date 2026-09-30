# Results

| Date | Change / opponent | Matches (games) | Win rate | 95% CI | Throughput / notes |
|---|---|---:|---:|---:|---|
| 2026-09-30 | Arena smoke/benchmark, random vs random | 4 (10) | 50.0% | 15.0%–85.0% | 44,368.7 games/hour/core, 2 workers; 0 errors |
| 2026-09-30 | Initial fixed-order heuristic vs random | 20 (41) | 0.0% | 0.0%–16.1% | 0 errors; rejected as a baseline |
| 2026-09-30 | Randomized equal-score ties only vs random | 20 (43) | 0.0% | 0.0%–16.1% | 0 errors; fixed-order bias was not the cause |
| 2026-09-30 | Develop before attacking vs random | 20 (47) | 90.0% | 69.9%–97.2% | 0 errors; current baseline candidate |
| 2026-09-30 | WSL Linux benchmark, random vs random | 10 (25) | 60.0% | 31.3%–83.2% | 69,375.4 games/hour/core, 2 workers; 0 errors |
| 2026-09-30 | WSL Linux baseline vs random | 20 (42) | 100.0% | 83.9%–100.0% | 0 errors; Linux `libcg.so` path |
| 2026-09-30 | Current baseline vs random | 50 (118) | 88.0% | 76.2%–94.4% | 0 errors; Windows local arena |
| 2026-09-30 | Deck round robin: sample vs two single-card Cyrano swaps | 30 (76) | 50.0% top average | exploratory; 3 decks | 60/60 matches resolved, 0 errors; no candidate beat the sample |
| 2026-09-30 | Reused ymgaq Mega Abomasnow rule agent vs current baseline | 50 (119) | 84.0% | 71.5%–91.7% | 0 errors; public Apache-2.0 policy plus its bundled deck; policy and deck effects are confounded |
| 2026-09-30 | ymgaq deck with current baseline policy vs current baseline | 50 (122) | 32.0% | 20.8%–45.8% | 0 errors; deck-only control is weaker, so the ymgaq policy is the main improvement |
| 2026-09-30 | Reused ymgaq Mega Abomasnow rule agent vs current baseline, confirmation | 100 (241) | 91.0% | 83.8%–95.2% | 0 errors; current local leader |

Win rates use match outcomes and Wilson 95% intervals. Throughput is from the local Windows x64 engine and is not a Kaggle-runtime measurement. The native game RNG cannot be seeded through the bundled wrapper, so repeated seeds do not fully reproduce games.

Startup follow-up (2026-09-30): embedded the verified sample deck as a fallback when runtime file paths cannot resolve `deck.csv`; the no-file regression test returns 60 legal card IDs. Rebuilt `submission.tar.gz`; its Linux package smoke test completed one BO3 match with no errors. This is a packaging check, not a performance estimate.

Ladder rank: not available. Kaggle public score is available, but the leaderboard rank was not captured.

Kaggle submission follow-up (2026-09-30): submission 56699815 completed successfully with public score 605.8. The result episode 115643067 finished with agent 0 reward 1 and agent 1 reward -1. The source-loaded deck fix removed the `__file__` dependency and matched the archived 60-card deck.