import argparse
import csv
from pathlib import Path
import shutil
import tempfile
import time

from deck_check import DEFAULT_CARD_DATA, load_card_data, read_deck, validate_deck
from arena import run_arena


ROOT = Path(__file__).resolve().parents[1]


def _prepare_agent(folder, name, deck_path, baseline_main):
    agent_dir = Path(folder) / name
    agent_dir.mkdir(parents=True)
    shutil.copyfile(baseline_main, agent_dir / "main.py")
    shutil.copyfile(deck_path, agent_dir / "deck.csv")
    return agent_dir


def run_roundrobin(deck_dir, matches_per_pair, workers, timeout, seed, output_dir, baseline_main=None):
    deck_dir = Path(deck_dir).resolve()
    deck_paths = sorted(deck_dir.glob("*.csv"))
    if not deck_paths:
        raise ValueError(f"no deck CSV files found in {deck_dir}")
    if matches_per_pair < 2 or matches_per_pair % 2:
        raise ValueError("matches-per-pair must be an even number of at least 2")

    cards = load_card_data(DEFAULT_CARD_DATA)
    for path in deck_paths:
        errors = validate_deck(read_deck(path), cards)
        if errors:
            raise ValueError(f"{path.name} is invalid: {'; '.join(errors)}")

    names = [path.stem for path in deck_paths]
    matrix = {name: {opponent: None for opponent in names} for name in names}
    for name in names:
        matrix[name][name] = 0.5

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_main = Path(baseline_main or ROOT / "agents" / "baseline" / "main.py").resolve()
    if not baseline_main.is_file():
        raise FileNotFoundError(f"agent main file not found: {baseline_main}")
    pair_matches = matches_per_pair // 2

    with tempfile.TemporaryDirectory(prefix="ptcg_roundrobin_") as temporary:
        temporary = Path(temporary)
        agent_dirs = {
            name: _prepare_agent(temporary, name, path, baseline_main)
            for name, path in zip(names, deck_paths)
        }
        for left_index, left_name in enumerate(names):
            for right_name in names[left_index + 1 :]:
                forward_csv = output_dir / f"{left_name}_vs_{right_name}_forward.csv"
                reverse_csv = output_dir / f"{left_name}_vs_{right_name}_reverse.csv"
                forward = run_arena(
                    agent_dirs[left_name],
                    agent_dirs[right_name],
                    pair_matches,
                    workers,
                    timeout,
                    seed,
                    forward_csv,
                )
                reverse = run_arena(
                    agent_dirs[right_name],
                    agent_dirs[left_name],
                    pair_matches,
                    workers,
                    timeout,
                    seed,
                    reverse_csv,
                )

                left_wins = sum(row["winner"] == "agent_a" for row in forward)
                left_wins += sum(row["winner"] == "agent_b" for row in reverse)
                draws = sum(row["winner"] == "draw" for row in forward + reverse)
                resolved = sum(row["winner"] in {"agent_a", "agent_b", "draw"} for row in forward + reverse)
                rate = (left_wins + 0.5 * draws) / resolved if resolved else None
                matrix[left_name][right_name] = rate
                matrix[right_name][left_name] = 1 - rate if rate is not None else None

    with (output_dir / "matrix.csv").open("w", newline="", encoding="utf-8") as matrix_file:
        writer = csv.writer(matrix_file)
        writer.writerow(["deck"] + names)
        for name in names:
            writer.writerow([name] + [matrix[name][opponent] for opponent in names])

    scores = {}
    for name in names:
        rates = [matrix[name][opponent] for opponent in names if opponent != name and matrix[name][opponent] is not None]
        scores[name] = sum(rates) / len(rates) if rates else None
    ranking = sorted(
        ((name, rate) for name, rate in scores.items() if rate is not None),
        key=lambda item: item[1],
        reverse=True,
    )
    with (output_dir / "ranking.csv").open("w", newline="", encoding="utf-8") as ranking_file:
        writer = csv.writer(ranking_file)
        writer.writerow(["rank", "deck", "average_win_rate"])
        for position, (name, rate) in enumerate(ranking, 1):
            writer.writerow([position, name, rate])

    if len(names) < 2:
        print(f"Validated {len(names)} deck; no pairwise ranking possible. Add more CSVs to {deck_dir}.")
    else:
        print("Average win rate against other decks:")
        for position, (name, rate) in enumerate(ranking, 1):
            print(f"{position}. {name}: {rate:.1%}")
    print(f"Matrix and ranking: {output_dir}")
    return matrix, ranking


def main():
    parser = argparse.ArgumentParser(description="Run paired-seat deck round robin with the baseline policy")
    parser.add_argument("--deck-dir", default=str(ROOT / "decks"))
    parser.add_argument("--matches-per-pair", type=int, default=20, help="Even total matches, split across seat orders")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--agent-main", default=None, help="main.py used to pilot every deck")
    args = parser.parse_args()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or str(ROOT / "runs" / f"roundrobin_{timestamp}")
    try:
        run_roundrobin(
            args.deck_dir,
            args.matches_per_pair,
            args.workers,
            args.timeout,
            args.seed,
            output_dir,
            args.agent_main,
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"round robin failed: {exc}\n")


if __name__ == "__main__":
    main()