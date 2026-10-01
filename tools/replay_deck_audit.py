from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _read_deck(path: Path) -> list[int]:
    with path.open(newline="") as deck_file:
        return [int(row[0]) for row in csv.reader(deck_file) if row]


def _replay_decks(path: Path) -> list[list[int]]:
    replay = json.loads(path.read_text(encoding="utf-8"))
    for step in replay.get("steps", []):
        actions = [item.get("action") for item in step if isinstance(item, dict)]
        decks = [action for action in actions if isinstance(action, list) and len(action) == 60]
        if len(decks) == 2 and all(all(isinstance(card_id, int) for card_id in deck) for deck in decks):
            return decks
    raise ValueError(f"could not find two 60-card deck actions in {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare replay-submitted decks with local deck files.")
    parser.add_argument("replay", type=Path)
    parser.add_argument("local_decks", nargs="+", type=Path)
    args = parser.parse_args()

    replay_decks = _replay_decks(args.replay)
    local_decks = [_read_deck(path) for path in args.local_decks]
    print(f"replay decks: {len(replay_decks)}")
    for replay_index, replay_deck in enumerate(replay_decks):
        matches = [str(path) for path, deck in zip(args.local_decks, local_decks) if deck == replay_deck]
        label = ", ".join(matches) if matches else "no local exact match"
        print(f"replay agent {replay_index}: {label}")
    if len(local_decks) == 2:
        print(f"ordered pair exact: {local_decks == replay_decks}")
        print(f"swapped pair exact: {local_decks == list(reversed(replay_decks))}")


if __name__ == "__main__":
    main()
