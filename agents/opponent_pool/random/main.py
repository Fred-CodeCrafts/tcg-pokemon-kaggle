import csv
import random
from pathlib import Path


def _read_deck():
    for path in (Path(__file__).resolve().with_name("deck.csv"), Path("deck.csv")):
        try:
            with path.open(newline="") as deck_file:
                deck = [int(row[0]) for row in csv.reader(deck_file) if row]
            if len(deck) == 60:
                return deck
        except (OSError, ValueError, IndexError):
            continue
    return []


def agent(obs_dict):
    try:
        select = obs_dict.get("select")
        if select is None:
            return _read_deck()
        options = select.get("option") or []
        minimum = select.get("minCount", 0)
        maximum = select.get("maxCount", 0)
        if not (0 <= minimum <= maximum <= len(options)):
            return []
        return random.sample(range(len(options)), maximum)
    except Exception:
        return []