from __future__ import annotations

import csv
from pathlib import Path

from cg.api import OptionType, all_attack, all_card_data, to_observation_class

JOLTIK = 160
GALVANTULA = 161
TERAPAGOS = 176
NOCTOWL = 173
FAN_ROTOM = 174
FEZANDIPITI = 140
BLOODMOON_URSALUNA = 44
CORNERSTONE_OGERPON = 117
WELLSPRING_OGERPON = 108

POFFIN = 1086
ULTRA_BALL = 1121
TERA_ORB = 1127
ENERGY_SWITCH = 1116
NIGHT_STRETCHER = 1097
PRIME_CATCHER = 1088
CRISPIN = 1198
BOSS = 1182
BRIAR = 1201
JUDGE = 1213
ERI = 1186
AREA_ZERO = 1250

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


def _hand_card(state, index):
    hand = state.players[state.yourIndex].hand or []
    if isinstance(index, int) and 0 <= index < len(hand):
        return hand[index]
    return None


def _target(state, option):
    player = state.players[state.yourIndex]
    area = int(option.inPlayArea) if option.inPlayArea is not None else -1
    values = player.active if area == 4 else player.bench if area == 5 else []
    if isinstance(option.inPlayIndex, int) and 0 <= option.inPlayIndex < len(values):
        return values[option.inPlayIndex]
    return None


def _ability_target(state, option):
    player = state.players[state.yourIndex]
    area = int(option.area) if option.area is not None else -1
    values = player.active if area == 4 else player.bench if area == 5 else []
    if isinstance(option.index, int) and 0 <= option.index < len(values):
        return values[option.index]
    return None


def _has_tera(player):
    return any(
        pokemon is not None
        and pokemon.id in (GALVANTULA, TERAPAGOS, CORNERSTONE_OGERPON, WELLSPRING_OGERPON)
        for pokemon in (player.active or []) + (player.bench or [])
    )


def _score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    kind = option.type

    if kind == OptionType.END:
        return -100
    if kind == OptionType.ATTACK:
        attack = attack_data.get(option.attackId)
        attack_name = getattr(attack, "name", "").lower() if attack else ""
        text = getattr(attack, "text", "").lower() if attack else ""
        damage = getattr(attack, "damage", 0) if attack else 0
        opponent = state.players[1 - state.yourIndex]
        enemy = opponent.active[0] if opponent.active else None
        enemy_data = card_data.get(enemy.id) if enemy is not None else None
        score = 40 + damage / 10
        if attack_name == "fulgurite" or "can't play any item" in text or "cannot play any item" in text:
            score += 180
        if attack_name == "crown opal":
            score += 80
        if "prevent all damage" in text and "basic" in text and enemy_data is not None:
            if str(getattr(enemy_data, "stage", "")).lower().startswith("basic"):
                score += 130
        if enemy is not None and damage >= enemy.hp > 0:
            score += 250
        return score
    if kind == OptionType.EVOLVE:
        card = _hand_card(state, option.index)
        card_id = getattr(card, "id", None)
        if card_id == NOCTOWL and _has_tera(player):
            return 165
        if card_id == GALVANTULA:
            return 155
        return 120
    if kind == OptionType.ABILITY:
        target = _ability_target(state, option)
        card_id = getattr(target, "id", None)
        if card_id == NOCTOWL:
            return 175 if _has_tera(player) else 90
        if card_id == FAN_ROTOM:
            return 155
        if card_id == FEZANDIPITI:
            return 125
        return 75
    if kind == OptionType.ATTACH:
        target = _target(state, option)
        energy = _hand_card(state, option.index)
        if target is None:
            return 50
        attached = len(getattr(target, "energies", []))
        if target.id == JOLTIK and attached == 0:
            return 170
        if target.id == JOLTIK:
            return 50
        if target.id == GALVANTULA:
            return 140 if attached < 3 else 70
        if target.id == TERAPAGOS:
            return 105 if attached < 3 else 65
        if target.id in (CORNERSTONE_OGERPON, WELLSPRING_OGERPON, BLOODMOON_URSALUNA):
            return 75 if attached < 3 else 55
        return 15 if energy is not None else 10
    if kind == OptionType.PLAY:
        card = _hand_card(state, option.index)
        card_id = getattr(card, "id", None)
        data = card_data.get(card_id)
        card_type = getattr(getattr(data, "cardType", None), "name", "")
        text = " ".join(getattr(skill, "text", "") for skill in getattr(data, "skills", [])).lower()
        if card_id == POFFIN:
            return 155 if state.turn <= 3 else 100
        if card_id in (ULTRA_BALL, TERA_ORB):
            return 140 if state.turn <= 4 else 105
        if card_id == CRISPIN:
            return 125
        if card_id in (BOSS, PRIME_CATCHER):
            return 100
        if card_id in (NIGHT_STRETCHER, ENERGY_SWITCH):
            return 95
        if card_id in (BRIAR, JUDGE, ERI):
            return 80
        if card_id == AREA_ZERO:
            return 90
        if card_type == "POKEMON":
            return 125 if state.turn <= 2 else 85
        if card_type == "SUPPORTER":
            return 100 if "search" in text or "draw" in text else 75
        if card_type == "ITEM":
            return 95 if "search" in text or "energy" in text else 70
        return 60
    if kind == OptionType.RETREAT:
        return 25
    if kind == OptionType.YES:
        return 5
    if kind == OptionType.NO:
        return 0

    context = getattr(observation.select.context, "name", "")
    if "EVOLVE" in context:
        return 140
    if "BENCH" in context:
        return 115
    if "ACTIVE" in context:
        return 105
    if "ATTACH" in context:
        return 100
    if "DISCARD" in context:
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
            key=lambda index: _score(
                observation.select.option[index], observation, card_data, attack_data
            ),
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