import argparse
import csv
import importlib.util
import random
import sys
from pathlib import Path

from arena import _choose_first_player, _fallback, _legalize, _load_deck


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CG = (
    ROOT
    / "the-pokemon-company-ptcg-ai-battle-challenge-playground"
    / "sample_submission"
    / "sample_submission"
    / "sample_submission"
)
LOSS_FIELDS = [
    "match_id",
    "game",
    "turn",
    "reason",
    "dragapult_seen",
    "dragapult_active",
    "phantom_dive_attacks",
    "phantom_energy_blocked_turns",
    "ready_phantom_turns",
    "immediate_spread_knockouts",
]


def _load_module(agent_dir, name):
    main_path = Path(agent_dir) / "main.py"
    spec = importlib.util.spec_from_file_location(name, main_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {main_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "agent", None)):
        raise AttributeError(f"{main_path} must define agent(obs_dict)")
    return module


def _loss_reason(metrics):
    if not metrics["dragapult_seen"]:
        return "Dragapult_never_evolved"
    if not metrics["dragapult_active"]:
        return "Dragapult_never_reached_Active"
    if metrics["phantom_dive_attacks"] == 0:
        if metrics["phantom_energy_blocked_turns"]:
            return "Phantom_Dive_missing_Fire_or_Psychic"
        return "Phantom_Dive_never_used"
    if metrics["immediate_spread_knockouts"] == 0:
        return "Phantom_Dive_spread_did_not_take_a_KO"
    return "Lost_prize_race_after_spread_KO"


def run_diagnostics(agent_a, agent_b, matches, timeout_steps, seed, output):
    if str(SAMPLE_CG) not in sys.path:
        sys.path.insert(0, str(SAMPLE_CG))
    from cg.api import SelectContext, all_attack, all_card_data, to_observation_class
    from cg.game import battle_finish, battle_select, battle_start

    agent_a = Path(agent_a).resolve()
    agent_b = Path(agent_b).resolve()
    decks = [_load_deck(agent_a), _load_deck(agent_b)]
    attack_data = {attack.attackId: attack for attack in all_attack()}
    phantom_id = next(
        (attack.attackId for attack in attack_data.values() if attack.name.lower() == "phantom dive"),
        None,
    )
    if phantom_id is None:
        raise RuntimeError("engine card data has no Phantom Dive attack")

    losses = []
    series_wins = [0, 0]
    games_played = 0
    agent_errors = 0

    for match_id in range(matches):
        random.seed(seed + match_id)
        agents = [
            _load_module(agent_a, f"drag_diag_a_{match_id}"),
            _load_module(agent_b, f"drag_diag_b_{match_id}"),
        ]
        game_wins = [0, 0]
        for game_index in range(3):
            observation, start_data = battle_start(decks[0], decks[1], reverse_player=True)
            if observation is None:
                raise RuntimeError(
                    f"engine rejected deck: player={start_data.errorPlayer}, type={start_data.errorType}"
                )

            metrics = {
                "dragapult_seen": False,
                "dragapult_active": False,
                "phantom_dive_attacks": 0,
                "phantom_energy_blocked_turns": 0,
                "ready_phantom_turns": 0,
                "immediate_spread_knockouts": 0,
                "turn": 0,
                "blocked_turns": set(),
                "ready_turns": set(),
            }
            try:
                for _ in range(timeout_steps):
                    state = observation.get("current") or {}
                    if state.get("result", -1) >= 0:
                        result = state["result"]
                        break

                    select = observation.get("select")
                    if not isinstance(select, dict):
                        raise RuntimeError("engine returned no legal selection")
                    options = select.get("option") or []
                    player = state.get("yourIndex", -1)
                    metrics["turn"] = max(metrics["turn"], state.get("turn", 0))

                    if player == 0:
                        typed = to_observation_class(observation)
                        own_state = typed.current.players[0]
                        board = [
                            pokemon
                            for pokemon in (own_state.active or []) + (own_state.bench or [])
                            if pokemon is not None
                        ]
                        dragapults = [pokemon for pokemon in board if pokemon.id == 121]
                        if dragapults:
                            metrics["dragapult_seen"] = True
                        if own_state.active and own_state.active[0] is not None:
                            if own_state.active[0].id == 121:
                                metrics["dragapult_active"] = True
                        if dragapults:
                            deficits = [
                                agents[0]._attack_deficit(
                                    pokemon,
                                    attack_data[phantom_id],
                                    agents[0]._metadata()[0],
                                )
                                for pokemon in dragapults
                            ]
                            if min(deficits) == 0:
                                metrics["ready_turns"].add(state.get("turn", 0))
                            else:
                                metrics["blocked_turns"].add(state.get("turn", 0))

                    forced = _choose_first_player(select, (match_id + game_index) % 2)
                    if forced is not None:
                        selection = forced
                    elif player in (0, 1):
                        try:
                            selection = agents[player].agent(observation)
                        except Exception:
                            agent_errors += 1
                            selection = _fallback(select)
                        selection = _legalize(selection, select)
                        if selection is None:
                            agent_errors += 1
                            selection = _fallback(select)
                    else:
                        raise RuntimeError(f"invalid acting player index {player}")

                    if player == 0:
                        for option_index in selection:
                            option = options[option_index]
                            if option.get("type") == 13 and option.get("attackId") == phantom_id:
                                metrics["phantom_dive_attacks"] += 1
                            if select.get("context") == SelectContext.DAMAGE_COUNTER_ANY and option.get("type") == 3:
                                target_player = option.get("playerIndex", 1)
                                target_zone = "active" if option.get("area") == 4 else "bench"
                                targets = state["players"][target_player].get(target_zone) or []
                                target_index = option.get("index", -1)
                                if 0 <= target_index < len(targets) and targets[target_index].get("hp", 1) <= 10:
                                    metrics["immediate_spread_knockouts"] += 1

                    observation = battle_select(selection)
                else:
                    raise TimeoutError(f"game exceeded {timeout_steps} decisions")
            finally:
                battle_finish()

            games_played += 1
            if result in (0, 1):
                game_wins[result] += 1
                if result == 1:
                    metrics["phantom_energy_blocked_turns"] = len(metrics["blocked_turns"])
                    metrics["ready_phantom_turns"] = len(metrics["ready_turns"])
                    metrics["reason"] = _loss_reason(metrics)
                    metrics["match_id"] = match_id
                    metrics["game"] = game_index + 1
                    losses.append({field: metrics.get(field) for field in LOSS_FIELDS})
            elif result != 2:
                raise RuntimeError(f"unexpected game result {result}")

            if max(game_wins) >= 2:
                break

        if game_wins[0] > game_wins[1]:
            series_wins[0] += 1
        elif game_wins[1] > game_wins[0]:
            series_wins[1] += 1

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as loss_file:
        writer = csv.DictWriter(loss_file, fieldnames=LOSS_FIELDS)
        writer.writeheader()
        writer.writerows(losses)
    print(
        f"Series: Dragapult {series_wins[0]}-{series_wins[1]} Abomasnow; "
        f"games: {games_played}; losses logged: {len(losses)}; "
        f"agent errors/invalid choices: {agent_errors}; diagnostics: {output}"
    )
    for reason in sorted({row["reason"] for row in losses}):
        count = sum(row["reason"] == reason for row in losses)
        print(f"{reason}: {count}")
    return losses


def main():
    parser = argparse.ArgumentParser(description="Log Dragapult loss reasons against an opponent pilot")
    parser.add_argument("--agent-a", default=str(ROOT / "agents" / "dragapult"))
    parser.add_argument("--agent-b", default=str(ROOT / "agents" / "ymgaq_abomasnow"))
    parser.add_argument("--matches", type=int, default=20)
    parser.add_argument("--timeout-steps", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--output", default=str(ROOT / "runs" / "dragapult_abomasnow_losses.csv"))
    args = parser.parse_args()
    if args.matches < 1 or args.timeout_steps < 1:
        parser.error("matches and timeout-steps must be positive")
    run_diagnostics(
        args.agent_a,
        args.agent_b,
        args.matches,
        args.timeout_steps,
        args.seed,
        args.output,
    )


if __name__ == "__main__":
    main()