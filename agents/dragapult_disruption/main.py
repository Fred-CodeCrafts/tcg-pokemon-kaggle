from __future__ import annotations

import csv
from pathlib import Path

from cg.api import OptionType, all_attack, all_card_data, to_observation_class

DREEPY = 119
DRAKLOAK = 120
DRAGAPULT = 121
DUSKULL = 131
DUSCLOPS = 132
DUSKNOIR = 133
TATSUGIRI = 122
FEZANDIPITI = 140
BUDEW = 235
LATIAS = 184
RARE_CANDY = 1079
POFFIN = 1086
ULTRA_BALL = 1121
NIGHT_STRETCHER = 1097
PRIME_CATCHER = 1088
LILLIE = 1227
BOSS = 1182
DAWN = 1231
CRISPIN = 1198
LUCKY_HELMET = 1156
COMMUNITY_CENTER = 1242
JAMMING_TOWER = 1246
PHANTOM_DIVE = 154
FIRE = 2
PSYCHIC = 5

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


def _energy_match(card, target, card_data):
    if card is None or target is None:
        return 0
    energy_data = card_data.get(card.id)
    energy_type = getattr(getattr(energy_data, "energyType", None), "value", None)
    if energy_type is None:
        return 0
    attached = {getattr(energy, "value", int(energy)) for energy in getattr(target, "energies", [])}
    target_data = card_data.get(target.id)
    best = 0
    for attack_id in getattr(target_data, "attacks", []) if target_data else []:
        attack = _ATTACK_DATA.get(attack_id)
        if attack is None:
            continue
        required = [getattr(energy, "value", int(energy)) for energy in attack.energies]
        missing = required.count(energy_type) - sum(energy == energy_type for energy in attached)
        best = max(best, missing)
    return best


def _keywords(card_data):
    skills = getattr(card_data, "skills", []) if card_data else []
    return " ".join(getattr(skill, "text", "") for skill in skills).lower()


def _score(option, obs, card_data, attack_data):
    state = obs.current
    kind = option.type
    if kind == OptionType.END:
        return -100
    if kind == OptionType.ATTACK:
        attack = attack_data.get(option.attackId)
        damage = getattr(attack, "damage", 0) if attack else 0
        opponent = state.players[1 - state.yourIndex].active
        hp = opponent[0].hp if opponent and opponent[0] is not None else 0
        score = 30 + damage / 10
        if damage >= hp > 0:
            score += 250
        if option.attackId == PHANTOM_DIVE:
            score += 50
        return score
    if kind == OptionType.EVOLVE:
        return 130
    if kind == OptionType.ABILITY:
        card_id = option.cardId
        if card_id == DRAKLOAK:
            return 150
        if card_id == DUSKNOIR:
            return 105
        if card_id == DUSCLOPS:
            return 85
        if card_id == FEZANDIPITI:
            return 90
        return 80
    if kind == OptionType.ATTACH:
        target = _target(state, option)
        card = _hand_card(state, option.index)
        score = 70 + 20 * _energy_match(card, target, card_data)
        if target is not None and target.id == DRAGAPULT:
            score += 20
        return score
    if kind == OptionType.PLAY:
        card = _hand_card(state, option.index)
        card_id = getattr(card, "id", None)
        data = card_data.get(card_id)
        card_type = getattr(getattr(data, "cardType", None), "name", "")
        text = _keywords(data)
        if card_id == RARE_CANDY:
            return 145
        if card_id == POFFIN:
            return 125 if state.turn <= 3 else 95
        if card_id == ULTRA_BALL:
            return 110
        if card_id == NIGHT_STRETCHER:
            return 90
        if card_id == CRISPIN:
            return 105
        if card_id in (LILLIE, DAWN):
            return 100
        if card_id == BOSS:
            return 80
        if card_id in (PRIME_CATCHER,):
            return 85
        if card_type == "POKEMON":
            return 90
        if card_type == "SUPPORTER":
            return 75 + (15 if "draw" in text or "search" in text else 0)
        if card_type == "ITEM":
            return 80 + (15 if "search" in text or "energy" in text else 0)
        if card_type == "TOOL":
            return 55
        if card_type == "STADIUM":
            return 45
        return 60
    if kind == OptionType.RETREAT:
        return 20
    if kind == OptionType.YES:
        return 5
    if kind == OptionType.NO:
        return 0
    context = getattr(obs.select.context, "name", "")
    if "EVOLVE" in context:
        return 130
    if "BENCH" in context:
        return 110
    if "ACTIVE" in context:
        return 100
    if "ATTACH" in context:
        return 90
    if "DISCARD" in context:
        return 20
    return 10


def _agent_impl(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return _read_deck()
    card_data, attack_data = _metadata()
    ranked = sorted(
        range(len(obs.select.option)),
        key=lambda index: _score(obs.select.option[index], obs, card_data, attack_data),
        reverse=True,
    )
    return ranked[: obs.select.maxCount]


def agent(obs_dict):
    try:
        return _agent_impl(obs_dict)
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
