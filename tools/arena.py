import argparse
import csv
import importlib.util
import multiprocessing as mp
from multiprocessing.connection import wait
import os
from pathlib import Path
import random
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CG = (
    ROOT
    / "the-pokemon-company-ptcg-ai-battle-challenge-playground"
    / "sample_submission"
    / "sample_submission"
    / "sample_submission"
)
RESULT_FIELDS = [
    "match_id",
    "agent_a",
    "agent_b",
    "winner",
    "games_played",
    "a_game_wins",
    "b_game_wins",
    "turns",
    "duration_s",
    "errors",
    "seed",
]


def _load_deck(agent_dir):
    deck_path = Path(agent_dir) / "deck.csv"
    with deck_path.open(newline="") as deck_file:
        deck = [int(row[0]) for row in csv.reader(deck_file) if row]
    if len(deck) != 60:
        raise ValueError(f"{deck_path} must contain exactly 60 card IDs")
    return deck


def _load_agent(agent_dir, unique_name):
    main_path = Path(agent_dir) / "main.py"
    spec = importlib.util.spec_from_file_location(unique_name, main_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {main_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "agent", None)):
        raise AttributeError(f"{main_path} must define agent(obs_dict)")
    return module.agent


def _fallback(select):
    options = select.get("option") or []
    minimum = select.get("minCount", 0)
    maximum = select.get("maxCount", 0)
    if not (isinstance(minimum, int) and isinstance(maximum, int)):
        return []
    if minimum < 0 or maximum < minimum or maximum > len(options):
        return []
    return list(range(maximum))


def _legalize(selection, select):
    options = select.get("option") or []
    minimum = select.get("minCount", 0)
    maximum = select.get("maxCount", 0)
    valid_bounds = (
        isinstance(minimum, int)
        and isinstance(maximum, int)
        and 0 <= minimum <= maximum <= len(options)
    )
    if not valid_bounds or not isinstance(selection, list):
        return None
    if not minimum <= len(selection) <= maximum:
        return None
    if any(type(index) is not int or not 0 <= index < len(options) for index in selection):
        return None
    if len(set(selection)) != len(selection):
        return None
    return selection


def _choose_first_player(select, wanted_player):
    if select.get("context") != 41 or select.get("minCount") != 1 or select.get("maxCount") != 1:
        return None
    wanted_type = 1 if wanted_player == 1 else 2
    for index, option in enumerate(select.get("option") or []):
        if isinstance(option, dict) and option.get("type") == wanted_type:
            return [index]
    return None


def _run_match(send_pipe, active_player, games_done, turns_done, agent_a_dir, agent_b_dir, match_id, seed):
    started_at = time.perf_counter()
    errors = []
    wins = [0, 0]
    turns_total = 0
    games_played = 0
    winner = "error"
    agent_dirs = [agent_a_dir, agent_b_dir]
    try:
        if str(SAMPLE_CG) not in sys.path:
            sys.path.insert(0, str(SAMPLE_CG))
        from cg.game import battle_finish, battle_select, battle_start

        agents = [
            _load_agent(agent_a_dir, f"agent_a_{match_id}"),
            _load_agent(agent_b_dir, f"agent_b_{match_id}"),
        ]
        decks = [_load_deck(agent_a_dir), _load_deck(agent_b_dir)]
        random.seed(seed)

        for game_index in range(3):
            wanted_first = (match_id + game_index) % 2
            active_player.value = -1
            observation, start_data = battle_start(decks[0], decks[1], reverse_player=True)
            if observation is None:
                raise RuntimeError(
                    f"engine rejected a deck (player={start_data.errorPlayer}, type={start_data.errorType})"
                )

            game_turns = 0
            try:
                for _ in range(10000):
                    current = observation.get("current") or {}
                    if current.get("result", -1) >= 0:
                        game_winner = current["result"]
                        break

                    select = observation.get("select")
                    if not isinstance(select, dict):
                        raise RuntimeError("engine returned no legal selection")

                    forced = _choose_first_player(select, wanted_first)
                    player = current.get("yourIndex", -1)
                    if forced is not None:
                        selection = forced
                    elif player in (0, 1):
                        active_player.value = player
                        try:
                            selection = agents[player](observation)
                        except Exception as exc:
                            errors.append(f"game {game_index + 1}, player {player}: {type(exc).__name__}: {exc}")
                            selection = _fallback(select)
                        selection = _legalize(selection, select)
                        if selection is None:
                            errors.append(f"game {game_index + 1}, player {player}: invalid selection")
                            selection = _fallback(select)
                    else:
                        raise RuntimeError(f"invalid acting player index: {player}")

                    observation = battle_select(selection)
                    game_turns = max(game_turns, (observation.get("current") or {}).get("turn", 0))
                else:
                    raise TimeoutError("game exceeded 10000 decisions")
            finally:
                battle_finish()

            games_played += 1
            games_done.value = games_played
            turns_total += game_turns
            turns_done.value = turns_total
            if game_winner not in (0, 1):
                raise RuntimeError(f"engine returned unexpected result: {game_winner}")
            wins[game_winner] += 1
            if max(wins) >= 2:
                break

        winner = "agent_a" if wins[0] > wins[1] else "agent_b"
    except BaseException as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        active = active_player.value
        if active in (0, 1):
            winner = "agent_b" if active == 0 else "agent_a"
    finally:
        send_pipe.send(
            {
                "match_id": match_id,
                "agent_a": Path(agent_a_dir).name,
                "agent_b": Path(agent_b_dir).name,
                "winner": winner,
                "games_played": games_played,
                "a_game_wins": wins[0],
                "b_game_wins": wins[1],
                "turns": turns_total,
                "duration_s": round(time.perf_counter() - started_at, 6),
                "errors": " | ".join(errors),
                "seed": seed,
            }
        )
        send_pipe.close()


def _wilson_interval(wins, games, z=1.959963984540054):
    if games == 0:
        return None, None
    rate = wins / games
    denominator = 1 + z * z / games
    center = (rate + z * z / (2 * games)) / denominator
    margin = z * ((rate * (1 - rate) / games + z * z / (4 * games * games)) ** 0.5) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def run_arena(agent_a, agent_b, matches, workers, timeout, seed, output, benchmark=False):
    agent_a = str(Path(agent_a).resolve())
    agent_b = str(Path(agent_b).resolve())
    for agent_dir in (agent_a, agent_b):
        if not (Path(agent_dir) / "main.py").is_file() or not (Path(agent_dir) / "deck.csv").is_file():
            raise FileNotFoundError(f"{agent_dir} must contain main.py and deck.csv")

    context = mp.get_context("spawn")
    pending = iter(range(matches))
    running = {}
    rows = []
    started_at = time.perf_counter()
    exhausted = False

    while running or not exhausted:
        while not exhausted and len(running) < workers:
            try:
                match_id = next(pending)
            except StopIteration:
                exhausted = True
                break
            match_seed = seed + match_id if seed is not None else random.randrange(2**31)
            receive_pipe, send_pipe = context.Pipe(duplex=False)
            active_player = context.Value("i", -1)
            games_done = context.Value("i", 0)
            turns_done = context.Value("i", 0)
            process = context.Process(
                target=_run_match,
                args=(send_pipe, active_player, games_done, turns_done, agent_a, agent_b, match_id, match_seed),
            )
            process.start()
            send_pipe.close()
            running[match_id] = {
                "process": process,
                "pipe": receive_pipe,
                "active_player": active_player,
                "games_done": games_done,
                "turns_done": turns_done,
                "started": time.perf_counter(),
                "seed": match_seed,
            }

        if not running:
            continue

        ready = wait([item["pipe"] for item in running.values()], timeout=0.1)
        ready_set = set(ready)
        now = time.perf_counter()
        for match_id, item in list(running.items()):
            process = item["process"]
            pipe = item["pipe"]
            row = None
            if pipe in ready_set:
                try:
                    row = pipe.recv()
                except EOFError:
                    row = None
            if row is None and not process.is_alive():
                row = {
                    "match_id": match_id,
                    "agent_a": Path(agent_a).name,
                    "agent_b": Path(agent_b).name,
                    "winner": "error",
                    "games_played": item["games_done"].value,
                    "a_game_wins": 0,
                    "b_game_wins": 0,
                    "turns": item["turns_done"].value,
                    "duration_s": round(now - item["started"], 6),
                    "errors": f"worker exited with code {process.exitcode} without a result",
                    "seed": item["seed"],
                }
            if row is None and now - item["started"] >= timeout:
                active = item["active_player"].value
                process.terminate()
                process.join()
                row = {
                    "match_id": match_id,
                    "agent_a": Path(agent_a).name,
                    "agent_b": Path(agent_b).name,
                    "winner": "agent_b" if active == 0 else "agent_a" if active == 1 else "error",
                    "games_played": item["games_done"].value,
                    "a_game_wins": 0,
                    "b_game_wins": 0,
                    "turns": item["turns_done"].value,
                    "duration_s": round(now - item["started"], 6),
                    "errors": f"match timed out after {timeout:g}s",
                    "seed": item["seed"],
                }
            if row is not None:
                if process.is_alive():
                    process.join(timeout=0.2)
                    if process.is_alive():
                        process.terminate()
                        process.join()
                pipe.close()
                rows.append(row)
                del running[match_id]

    elapsed = time.perf_counter() - started_at
    rows.sort(key=lambda row: row["match_id"])
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as result_file:
        writer = csv.DictWriter(result_file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    wins_a = sum(row["winner"] == "agent_a" for row in rows)
    wins_b = sum(row["winner"] == "agent_b" for row in rows)
    draws = sum(row["winner"] == "draw" for row in rows)
    resolved = wins_a + wins_b + draws
    rate = (wins_a + 0.5 * draws) / resolved if resolved else 0.0
    low, high = _wilson_interval(wins_a + 0.5 * draws, resolved)
    errors = sum(bool(row["errors"]) for row in rows)
    games = sum(row["games_played"] for row in rows)
    print(f"Matches: {len(rows)} ({resolved} resolved, {errors} with errors); games: {games}")
    if low is None:
        print("Agent A win rate: unavailable (no resolved matches)")
    else:
        print(f"Agent A win rate: {rate:.1%} (95% Wilson CI {low:.1%}-{high:.1%}, n={resolved})")
    print(f"Elapsed: {elapsed:.2f}s; results: {output_path}")
    if benchmark:
        games_per_hour_core = games * 3600 / elapsed / workers if elapsed else 0.0
        print(f"Throughput: {games_per_hour_core:.1f} games/hour/core ({workers} workers)")
    return rows


def main():
    parser = argparse.ArgumentParser(description="Run parallel best-of-three cabt matches")
    parser.add_argument("--agent-a", required=True, help="Agent directory containing main.py and deck.csv")
    parser.add_argument("--agent-b", required=True, help="Agent directory containing main.py and deck.csv")
    parser.add_argument("--matches", type=int, default=10)
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-match timeout in seconds")
    parser.add_argument("--seed", type=int, default=None, help="Seeds agent-side randomness and match scheduling")
    parser.add_argument("--output", default=None, help="CSV path (default: runs/arena_TIMESTAMP.csv)")
    parser.add_argument("--benchmark", action="store_true", help="Also print games/hour/core")
    args = parser.parse_args()
    if args.matches < 1 or args.workers < 1 or args.timeout <= 0:
        parser.error("matches, workers, and timeout must be positive")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output = args.output or str(ROOT / "runs" / f"arena_{timestamp}.csv")
    run_arena(args.agent_a, args.agent_b, args.matches, args.workers, args.timeout, args.seed, output, args.benchmark)


if __name__ == "__main__":
    mp.freeze_support()
    main()