from __future__ import annotations

import csv
from pathlib import Path

from cg.api import OptionType, all_attack, all_card_data, to_observation_class

_CARD_DATA = None
_ATTACK_DATA = None


def _read_deck():
    for path in (Path(__file__).with_name("deck.csv"), Path("deck.csv")):
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


def _score(option, observation, card_data, attack_data):
    if option.type == OptionType.END:
        return -100
    if option.type == OptionType.ATTACK:
        attack = attack_data.get(option.attackId)
        damage = getattr(attack, "damage", 0) if attack else 0
        return 30 + damage / 10
    if option.type == OptionType.ABILITY:
        return 105
    if option.type == OptionType.EVOLVE:
        return 100
    if option.type == OptionType.ATTACH:
        return 90
    if option.type == OptionType.PLAY:
        return 80
    if option.type == OptionType.RETREAT:
        return 20
    if option.type == OptionType.YES:
        return 5
    if option.type == OptionType.NO:
        return 0
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
