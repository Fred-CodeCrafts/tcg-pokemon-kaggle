from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from cg.api import AreaType, OptionType, SelectContext, all_attack, all_card_data, to_observation_class

STEVEN_BELDUM = 639
STEVEN_METANG = 640
STEVEN_METAGROSS = 641
GENESECT_EX = 547
MEGA_ABOMASNOW = 723
SNOVER = 722
METAL_ENERGY = 8

POFFIN = 1086
ULTRA_BALL = 1121
POKE_PAD = 1152
RARE_CANDY = 1079
CARMINE = 1192
LILLIE = 1227
CRISPIN = 1198
BOSS = 1182
SWITCH = 1123
PRIME_CATCHER = 1088
NIGHT_STRETCHER = 1097
GRAND_TREE = 1249

_CARD_DATA = None
_ATTACK_DATA = None
_TREE_STAGE_CARD_ID = None

CONFIG = {
    "find_beldum": 200,
    "find_stage": 195,
    "evolve_line": 190,
    "genesect_search": 185,
    "x_boot": 205,
    "draw_early": 175,
    "supporter": 140,
    "attach_to_line": 155,
    "attack": 55,
    "metal_stomp": 300,
    "setup_active": 180,
}


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


def _value(value):
    return getattr(value, "value", value)


def _context(observation):
    return _value(observation.select.context) if observation.select is not None else None


def _zone(state, area, player_index):
    if not isinstance(player_index, int) or not 0 <= player_index < len(state.players):
        return []
    player = state.players[player_index]
    area = _value(area)
    if area == AreaType.HAND:
        return player.hand or []
    if area == AreaType.DECK:
        return []
    if area == AreaType.DISCARD:
        return player.discard or []
    if area == AreaType.ACTIVE:
        return player.active or []
    if area == AreaType.BENCH:
        return player.bench or []
    if area == AreaType.PRIZE:
        return player.prize or []
    if area == AreaType.STADIUM:
        return state.stadium or []
    if area == AreaType.LOOKING:
        return state.looking or []
    return []


def _option_card(observation, option):
    area = getattr(option, "area", None)
    index = getattr(option, "index", None)
    player_index = getattr(option, "playerIndex", observation.current.yourIndex)
    if area is None or not isinstance(index, int):
        return None
    zone = observation.select.deck or [] if _value(area) == AreaType.DECK else _zone(
        observation.current, area, player_index
    )
    return zone[index] if 0 <= index < len(zone) else None


def _hand_card(state, index):
    hand = state.players[state.yourIndex].hand or []
    return hand[index] if isinstance(index, int) and 0 <= index < len(hand) else None


def _target(state, area, index, player_index):
    zone = _zone(state, area, player_index)
    return zone[index] if isinstance(index, int) and 0 <= index < len(zone) else None


def _board(player):
    return [card for card in (player.active or []) + (player.bench or []) if card is not None]


def _count(player, card_id):
    return sum(card.id == card_id for card in _board(player))


def _hand_ids(player):
    return [card.id for card in (player.hand or []) if card is not None]


def _attack_deficit(pokemon, attack, card_data, extra_metal=False):
    required = Counter(_value(item) for item in getattr(attack, "energies", []))
    generic = required.pop(0, 0)
    attached = Counter()
    total = 0
    for card in getattr(pokemon, "energyCards", []) or []:
        data = card_data.get(card.id)
        if data is None:
            continue
        attached[_value(data.energyType)] += 1
        total += 1
    if not getattr(pokemon, "energyCards", None):
        for energy in getattr(pokemon, "energies", []) or []:
            attached[_value(energy)] += 1
            total += 1
    if extra_metal:
        attached[METAL_ENERGY] += 1
        total += 1
    colored_used = sum(min(amount, attached[kind]) for kind, amount in required.items())
    colored_missing = sum(required.values()) - colored_used
    generic_missing = max(0, generic - max(0, total - colored_used))
    return colored_missing + generic_missing


def _metagross_ready(player, card_data, attack_data):
    for pokemon in _board(player):
        if pokemon.id != STEVEN_METAGROSS:
            continue
        for attack_id in card_data[STEVEN_METAGROSS].attacks:
            attack = attack_data.get(attack_id)
            if attack and _attack_deficit(pokemon, attack, card_data) == 0:
                return True
    return False


def _prizes_left(player):
    prizes = player.prize or []
    return prizes if isinstance(prizes, int) else len(prizes)


def _can_metal_stomp_ko(state, target, card_data, attack_data):
    player = state.players[state.yourIndex]
    for pokemon in _board(player):
        if pokemon.id != STEVEN_METAGROSS:
            continue
        for attack_id in card_data[STEVEN_METAGROSS].attacks:
            attack = attack_data.get(attack_id)
            if attack and attack.name.lower() == "metal stomp":
                return (
                    _attack_deficit(pokemon, attack, card_data) == 0
                    and target.hp <= attack.damage * 2
                )
    return False


def _card_score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    card = _option_card(observation, option)
    card_id = getattr(card, "id", None)
    context = _context(observation)
    if context == SelectContext.SETUP_ACTIVE_POKEMON:
        return CONFIG["setup_active"] if card_id == STEVEN_BELDUM else 90
    if context in (SelectContext.TO_BENCH, SelectContext.SETUP_BENCH_POKEMON):
        if card_id == STEVEN_BELDUM:
            return 160 - 20 * _count(player, STEVEN_BELDUM)
        if card_id == GENESECT_EX:
            return 150 - 20 * _count(player, GENESECT_EX)
        return 40
    if context == SelectContext.TO_HAND:
        if card_id == STEVEN_METAGROSS and not _count(player, STEVEN_METAGROSS):
            return 250
        if card_id == STEVEN_METANG and not _count(player, STEVEN_METANG):
            return 240
        if card_id == GENESECT_EX and not _count(player, GENESECT_EX):
            return 225
        if card_id == STEVEN_BELDUM and _count(player, STEVEN_BELDUM) < 2:
            return 210
        if card_id == RARE_CANDY:
            return 230
        return 25
    if context == SelectContext.EVOLVES_TO:
        if card_id == STEVEN_METANG:
            return 240
        if card_id == STEVEN_METAGROSS:
            return 250
        return 10
    if context == SelectContext.EVOLVES_FROM:
        if card_id == STEVEN_BELDUM and _TREE_STAGE_CARD_ID == STEVEN_METANG:
            return 240
        if card_id == STEVEN_METANG and _TREE_STAGE_CARD_ID == STEVEN_METAGROSS:
            return 250
        return 10
    if context in (SelectContext.ATTACH_FROM, SelectContext.ATTACH_TO):
        if card_id == METAL_ENERGY:
            return 260
        if card_id == STEVEN_METAGROSS:
            return 250
        return 5
    if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
        if card_id == STEVEN_METAGROSS and _metagross_ready(player, card_data, attack_data):
            return 500
        if card_id in (STEVEN_BELDUM, STEVEN_METANG):
            return 160
        return 35
    if context == SelectContext.DISCARD:
        if card_id == METAL_ENERGY:
            return 85
        if card_id in (STEVEN_BELDUM, STEVEN_METANG, STEVEN_METAGROSS, GENESECT_EX):
            return 5
        return 50
    return 20


def _play_score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    card = _hand_card(state, option.index)
    card_id = getattr(card, "id", None)
    hand_ids = _hand_ids(player)
    field_ids = [item.id for item in _board(player)]
    available = hand_ids + field_ids
    if card_id == POFFIN:
        return CONFIG["find_beldum"] if _count(player, STEVEN_BELDUM) < 2 else 90
    if card_id == ULTRA_BALL:
        need = not any(cid in available for cid in (GENESECT_EX, STEVEN_METAGROSS))
        return CONFIG["find_stage"] if need else 125
    if card_id == POKE_PAD:
        return CONFIG["find_stage"] if STEVEN_METANG not in available else 120
    if card_id == RARE_CANDY:
        old_beldum = any(item.id == STEVEN_BELDUM and not item.appearThisTurn for item in _board(player))
        return CONFIG["evolve_line"] if state.turn > 1 and old_beldum and STEVEN_METAGROSS in available else 15
    if card_id == CARMINE:
        return CONFIG["draw_early"] if state.turn <= 2 else 135
    if card_id == LILLIE:
        return CONFIG["draw_early"] if _prizes_left(player) == 6 or len(player.hand or []) <= 3 else 130
    if card_id == CRISPIN:
        return 155
    if card_id in (BOSS, PRIME_CATCHER):
        if any(_can_metal_stomp_ko(state, target, card_data, attack_data) for target in (opponent.bench or []) if target):
            return 185
        return 5
    if card_id == SWITCH:
        return 170 if _metagross_ready(player, card_data, attack_data) else 70
    if card_id == NIGHT_STRETCHER:
        return 120 if any(card.id in (STEVEN_BELDUM, STEVEN_METANG, STEVEN_METAGROSS, GENESECT_EX) for card in (player.discard or [])) else 90
    if card_id == GRAND_TREE:
        old_beldum = any(
            item.id == STEVEN_BELDUM and not item.appearThisTurn for item in _board(player)
        )
        return 200 if state.turn > 2 and old_beldum and not _count(player, STEVEN_METANG) else 60
    if card_id in (STEVEN_BELDUM, STEVEN_METANG, STEVEN_METAGROSS, GENESECT_EX):
        return 180 if not _count(player, card_id) else 85
    return 70


def _ability_source(state, option):
    return _target(state, option.area, option.index, state.yourIndex)


def _ability_score(option, observation):
    state = observation.current
    player = state.players[state.yourIndex]
    source = _ability_source(state, option)
    source_id = getattr(source, "id", None)
    ids = _hand_ids(player)
    field_ids = [item.id for item in _board(player)]
    if source_id == GENESECT_EX:
        return CONFIG["genesect_search"] if STEVEN_METANG not in ids or not _count(player, STEVEN_METANG) else 100
    if source_id == STEVEN_METAGROSS:
        return CONFIG["x_boot"]
    if source_id == GRAND_TREE:
        old_beldum = any(
            item.id == STEVEN_BELDUM and not item.appearThisTurn for item in _board(player)
        )
        return 210 if old_beldum and not _count(player, STEVEN_METANG) else 5
    return 25


def _energy_score(option, observation, card_data):
    state = observation.current
    target = _target(state, option.inPlayArea, option.inPlayIndex, state.yourIndex)
    energy = _hand_card(state, option.index)
    if target is None or energy is None or energy.id != METAL_ENERGY:
        return -100
    if target.id in (STEVEN_BELDUM, STEVEN_METANG, STEVEN_METAGROSS):
        attached = len(getattr(target, "energies", []))
        return CONFIG["attach_to_line"] + max(0, 3 - attached) * 25
    if target.id == GENESECT_EX:
        return 50
    return 5


def _score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    kind = option.type
    if kind == OptionType.CARD:
        return _card_score(option, observation, card_data, attack_data)
    if kind == OptionType.END:
        return -100
    if kind == OptionType.ABILITY:
        return _ability_score(option, observation)
    if kind == OptionType.EVOLVE:
        target = _target(state, option.inPlayArea, option.inPlayIndex, state.yourIndex)
        card = _hand_card(state, option.index)
        if getattr(card, "id", None) == STEVEN_METANG and getattr(target, "id", None) == STEVEN_BELDUM:
            return CONFIG["evolve_line"]
        if getattr(card, "id", None) == STEVEN_METAGROSS and getattr(target, "id", None) == STEVEN_METANG:
            return CONFIG["evolve_line"] + 5
        return 100
    if kind == OptionType.ATTACH:
        return _energy_score(option, observation, card_data)
    if kind == OptionType.PLAY:
        return _play_score(option, observation, card_data, attack_data)
    if kind == OptionType.ATTACK:
        attack = attack_data.get(option.attackId)
        if attack is None:
            return 20
        active = opponent.active[0] if opponent.active else None
        score = CONFIG["attack"] + attack.damage / 10
        if attack.name.lower() == "metal stomp" and active is not None and active.id == MEGA_ABOMASNOW:
            score += CONFIG["metal_stomp"]
        return score
    if kind == OptionType.RETREAT:
        return 15
    if kind == OptionType.YES:
        return 10
    if kind == OptionType.NO:
        return 0
    if kind == OptionType.NUMBER:
        return getattr(option, "number", 0)
    if _context(observation) == SelectContext.DRAW_COUNT:
        return getattr(option, "number", 0)
    return 10


def agent(obs_dict):
    global _TREE_STAGE_CARD_ID
    try:
        observation = to_observation_class(obs_dict)
        if observation.select is None:
            _TREE_STAGE_CARD_ID = None
            return _read_deck()
        card_data, attack_data = _metadata()
        options = observation.select.option
        context = _context(observation)
        ranked = sorted(
            range(len(options)),
            key=lambda index: _score(options[index], observation, card_data, attack_data),
            reverse=True,
        )
        selection = ranked[: observation.select.maxCount]
        if context == SelectContext.EVOLVES_TO and selection:
            card = _option_card(observation, options[selection[0]])
            _TREE_STAGE_CARD_ID = getattr(card, "id", None)
        elif context == SelectContext.EVOLVES_FROM:
            _TREE_STAGE_CARD_ID = None
        return selection
    except Exception:
        if isinstance(obs_dict, dict) and obs_dict.get("select") is None:
            return _read_deck()
        select = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if not isinstance(select, dict):
            return []
        options = select.get("option") or []
        minimum = select.get("minCount", 0)
        maximum = select.get("maxCount", 0)
        if isinstance(minimum, int) and isinstance(maximum, int) and 0 <= minimum <= maximum <= len(options):
            return list(range(maximum))
        return []
