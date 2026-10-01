from __future__ import annotations

import csv
from pathlib import Path

from cg.api import OptionType, all_attack, all_card_data, to_observation_class

_CARD_DATA = None
_ATTACK_DATA = None


def _read_deck():
    candidates = [Path(__file__).with_name("deck.csv"), Path("deck.csv")]
    for path in candidates:
        try:
            with path.open(newline="") as deck_file:
                deck = [int(row[0]) for row in csv.reader(deck_file) if row]
            if len(deck) == 60:
                return deck
        except (OSError, ValueError, IndexError):
            continue
    return []


def _metadata():
    global _CARD_DATA, _ATTACK_DATA
    if _CARD_DATA is None:
        _CARD_DATA = {card.cardId: card for card in all_card_data()}
        _ATTACK_DATA = {attack.attackId: attack for attack in all_attack()}
    return _CARD_DATA, _ATTACK_DATA


def _text(card_data):
    skills = getattr(card_data, "skills", []) if card_data is not None else []
    return " ".join(getattr(skill, "text", "") for skill in skills).lower()


def _card_from_hand(state, index):
    player = state.players[state.yourIndex]
    hand = player.hand or []
    if isinstance(index, int) and 0 <= index < len(hand):
        return hand[index]
    return None


def _target(state, option):
    player = state.players[state.yourIndex]
    area = getattr(option, "inPlayArea", None)
    index = getattr(option, "inPlayIndex", None)
    if area is None or not isinstance(index, int):
        return None
    values = player.active if int(area) == 4 else player.bench if int(area) == 5 else []
    if 0 <= index < len(values):
        return values[index]
    return None


def _needs_energy(target, card_data):
    if target is None or card_data is None:
        return False
    attached = len(getattr(target, "energies", []))
    attacks = getattr(card_data, "attacks", [])
    return bool(attacks) and attached < min(
        len(getattr(_ATTACK_DATA.get(attack_id), "energies", [])) for attack_id in attacks
    )


def _score(option, observation, card_data, attack_data):
    state = observation.current
    kind = option.type
    if kind == OptionType.END:
        return -100
    if kind == OptionType.ATTACK:
        attack = attack_data.get(option.attackId)
        damage = getattr(attack, "damage", 0) if attack else 0
        text = getattr(attack, "text", "").lower() if attack else ""
        active = state.players[1 - state.yourIndex].active
        hp = active[0].hp if active and active[0] is not None else 0
        return 30 + damage / 10 + (200 if damage >= hp > 0 else 0) + (10 if "bench" in text else 0)
    if kind == OptionType.ABILITY:
        card = card_data.get(option.cardId)
        text = _text(card)
        return 90 + (15 if "draw" in text or "search" in text else 0)
    if kind == OptionType.EVOLVE:
        return 95
    if kind == OptionType.ATTACH:
        target = _target(state, option)
        target_data = card_data.get(getattr(target, "id", None))
        return 70 + (15 if _needs_energy(target, target_data) else -20)
    if kind == OptionType.PLAY:
        card = _card_from_hand(state, option.index)
        data = card_data.get(getattr(card, "id", None))
        card_type = getattr(getattr(data, "cardType", None), "name", "")
        text = _text(data)
        if card_type == "POKEMON":
            return 75 + (10 if state.turn <= 2 else 0)
        if card_type == "SUPPORTER":
            return 65 + (20 if "draw" in text or "search" in text else 0)
        if card_type == "ITEM":
            return 70 + (20 if "search" in text or "energy" in text else 0)
        if card_type == "TOOL":
            return 50
        if card_type == "STADIUM":
            return 45
        return 60
    if kind == OptionType.RETREAT:
        return 20
    if kind == OptionType.YES:
        return 5
    if kind == OptionType.NO:
        return 0
    context = getattr(observation.select, "context", None)
    context_name = getattr(context, "name", "")
    if "EVOLVE" in context_name:
        return 90
    if "BENCH" in context_name or "ACTIVE" in context_name:
        return 80
    if "ATTACH" in context_name:
        return 75
    if "DISCARD" in context_name:
        return 20
    return 10


def agent(obs_dict):
    try:
        observation = to_observation_class(obs_dict)
        if observation.select is None:
            return _read_deck()
        card_data, attack_data = _metadata()
        ranked = sorted(
            range(len(observation.select.option)),
            key=lambda index: _score(observation.select.option[index], observation, card_data, attack_data),
            reverse=True,
        )
        return ranked[: observation.select.maxCount]
    except Exception:
        if isinstance(obs_dict, dict) and obs_dict.get("select") is None:
            return _read_deck()
        select = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if not isinstance(select, dict):
            return []
        options = select.get("option") or []
        maximum = select.get("maxCount", 0)
        minimum = select.get("minCount", 0)
        if isinstance(minimum, int) and isinstance(maximum, int) and 0 <= minimum <= maximum <= len(options):
            return list(range(maximum))
        return []
