import argparse
import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CARD_DATA = (
    ROOT
    / "the-pokemon-company-ptcg-ai-battle-challenge-playground"
    / "EN_Card_Data_R2_full.csv"
)


def load_card_data(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as card_file:
        reader = csv.DictReader(card_file)
        headers = reader.fieldnames or []
        stage_field = next((field for field in headers if field.startswith("Stage (")), None)
        if not {"Card ID", "Card Name", "Rule"}.issubset(headers) or stage_field is None:
            raise ValueError("card data is missing required ID, name, rule, or stage fields")

        cards = {}
        for row in reader:
            try:
                card_id = int(row["Card ID"])
            except (TypeError, ValueError):
                continue
            cards.setdefault(
                card_id,
                {
                    "name": row["Card Name"].strip(),
                    "rule": row["Rule"].strip(),
                    "stage": row[stage_field].strip(),
                },
            )
    return cards


def read_deck(path):
    card_ids = []
    with Path(path).open(encoding="utf-8-sig", newline="") as deck_file:
        for line_number, row in enumerate(csv.reader(deck_file), 1):
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) != 1:
                raise ValueError(f"line {line_number}: expected one card ID per row")
            value = row[0].strip()
            if line_number == 1 and value.casefold() in {"card id", "card_id", "id"}:
                continue
            try:
                card_ids.append(int(value))
            except ValueError as exc:
                raise ValueError(f"line {line_number}: {value!r} is not an integer card ID") from exc
    return card_ids


def validate_deck(card_ids, cards):
    errors = []
    if len(card_ids) != 60:
        errors.append(f"expected 60 cards, found {len(card_ids)}")

    unknown = sorted({card_id for card_id in card_ids if card_id not in cards})
    if unknown:
        errors.append(f"unknown card IDs: {', '.join(map(str, unknown))}")

    known_cards = [cards[card_id] for card_id in card_ids if card_id in cards]
    name_counts = Counter(card["name"] for card in known_cards if card["stage"] != "Basic Energy")
    over_limit = sorted((name, count) for name, count in name_counts.items() if count > 4)
    for name, count in over_limit:
        errors.append(f"{name}: {count} copies exceeds the 4-card limit")

    ace_specs = sum("ACE SPEC" in card["rule"].upper() for card in known_cards)
    if ace_specs > 1:
        errors.append(f"deck contains {ace_specs} ACE SPEC cards; maximum is 1")

    has_basic = any(card["stage"].startswith("Basic ") and card["stage"] != "Basic Energy" for card in known_cards)
    if not has_basic:
        errors.append("deck must contain at least one Basic Pokémon")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate a 60-card deck using competition card data")
    parser.add_argument("deck", help="CSV with one card ID per row")
    parser.add_argument("--card-data", default=str(DEFAULT_CARD_DATA))
    args = parser.parse_args()
    try:
        cards = load_card_data(args.card_data)
        errors = validate_deck(read_deck(args.deck), cards)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"deck check failed: {exc}\n")
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("VALID: 60 known cards, copy limits, ACE SPEC limit, and Basic Pokémon requirement passed")


if __name__ == "__main__":
    main()