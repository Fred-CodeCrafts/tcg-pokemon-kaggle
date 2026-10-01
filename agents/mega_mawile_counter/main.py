from __future__ import annotations

import csv
from pathlib import Path

from cg.api import AreaType, OptionType, SelectContext, all_attack, all_card_data, to_observation_class

MEGA_MAWILE = 695
GENESECT_EX = 547
BELDUM = 85
METANG = 86
BUDEW = 235
MEGA_ABOMASNOW = 723
SNOVER = 722

POFFIN = 1086
ULTRA_BALL = 1121
POKE_PAD = 1152
CARMINE = 1192
LILLIE = 1227
CRISPIN = 1198
BOSS = 1182
CRUSHING_HAMMER = 1120
SWITCH = 1123
NIGHT_STRETCHER = 1097
DAWN = 1231
GRAND_TREE = 1249
METAL_ENERGY = 8

FALLBACK_DECK = (
    (MEGA_MAWILE,) * 4
    + (GENESECT_EX,) * 3
    + (BELDUM,) * 4
    + (METANG,) * 4
    + (POFFIN,) * 4
    + (ULTRA_BALL,) * 4
    + (POKE_PAD,) * 4
    + (CARMINE,) * 3
    + (LILLIE,) * 3
    + (DAWN,) * 3
    + (BOSS,) * 2
    + (CRUSHING_HAMMER,) * 3
    + (SWITCH, NIGHT_STRETCHER, GRAND_TREE)
    + (METAL_ENERGY,) * 16
)

CONFIG = {
    "setup_search": 210,
    "stage_search": 195,
    "evolve_metang": 185,
    "genesect_search": 190,
    "metal_maker": 205,
    "grand_tree": 195,
    "supporter": 145,
    "draw_supporter_early": 175,
    "energy_attach": 120,
    "attack": 55,
    "mawile_attack_ready": 275,
    "bench_mawile": 165,
}

_CARD_DATA = None
_ATTACK_DATA = None
_TREE_STAGE_CARD_ID = None
_STARTER_ID = None


def _read_deck():
    paths = [Path("deck.csv")]
    module_file = globals().get("__file__")
    if module_file:
        paths.insert(0, Path(module_file).with_name("deck.csv"))
    for path in paths:
        try:
            with path.open(newline="") as deck_file:
                deck = [int(row[0]) for row in csv.reader(deck_file) if row]
            if len(deck) == 60:
                return deck
        except (OSError, ValueError, IndexError):
            continue
    return list(FALLBACK_DECK)


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


def _card_from_option(observation, option):
    area = getattr(option, "area", None)
    index = getattr(option, "index", None)
    player_index = getattr(option, "playerIndex", observation.current.yourIndex)
    if area is None or not isinstance(index, int):
        return None
    if _value(area) == AreaType.DECK:
        zone = observation.select.deck or []
    else:
        zone = _zone(observation.current, area, player_index)
    return zone[index] if 0 <= index < len(zone) else None


def _hand_card(state, index):
    hand = state.players[state.yourIndex].hand or []
    return hand[index] if isinstance(index, int) and 0 <= index < len(hand) else None


def _target(state, area, index, player_index):
    zone = _zone(state, area, player_index)
    return zone[index] if isinstance(index, int) and 0 <= index < len(zone) else None


def _pokemon(player):
    return [item for item in (player.active or []) + (player.bench or []) if item is not None]


def _count(player, card_id):
    return sum(item.id == card_id for item in _pokemon(player))


def _hand_ids(player):
    return [item.id for item in (player.hand or []) if item is not None]


def _source(state, option):
    return _target(state, option.area, option.index, state.yourIndex)


def _evolution_target(state, option):
    return _target(state, option.inPlayArea, option.inPlayIndex, state.yourIndex)


def _attack_deficit(pokemon, attack, card_data, extra_metal=False):
    requirements = {}
    for energy in getattr(attack, "energies", []):
        energy_type = _value(energy)
        requirements[energy_type] = requirements.get(energy_type, 0) + 1
    generic = requirements.pop(0, 0)
    attached = {}
    total = 0
    for card in getattr(pokemon, "energyCards", []) or []:
        data = card_data.get(card.id)
        if data is None:
            continue
        energy_type = _value(data.energyType)
        attached[energy_type] = attached.get(energy_type, 0) + 1
        total += 1
    if not getattr(pokemon, "energyCards", None):
        for energy in getattr(pokemon, "energies", []) or []:
            energy_type = _value(energy)
            attached[energy_type] = attached.get(energy_type, 0) + 1
            total += 1
    if extra_metal:
        attached[METAL_ENERGY] = attached.get(METAL_ENERGY, 0) + 1
        total += 1
    missing_colored = sum(max(0, amount - attached.get(kind, 0)) for kind, amount in requirements.items())
    used = sum(min(amount, attached.get(kind, 0)) for kind, amount in requirements.items())
    generic_missing = max(0, generic - (total - used))
    return missing_colored + generic_missing


def _mawile_ready(player, card_data, attack_data):
    for pokemon in _pokemon(player):
        if pokemon.id != MEGA_MAWILE:
            continue
        data = card_data.get(pokemon.id)
        for attack_id in data.attacks:
            attack = attack_data.get(attack_id)
            if attack and attack.name.lower() == "huge bite":
                if _attack_deficit(pokemon, attack, card_data) == 0:
                    return True
    return False


def _mawile_attack_damage(target, attack, card_data, prizes_taken=0):
    damage = getattr(attack, "damage", 0)
    attack_name = attack.name.lower()
    if attack_name == "gobble down":
        damage = 80 * max(0, prizes_taken)
    elif attack_name == "huge bite" and target.hp < target.maxHp:
        damage = 30
    target_data = card_data.get(target.id)
    attacker_data = card_data.get(MEGA_MAWILE)
    weakness = _value(getattr(target_data, "weakness", None)) if target_data else None
    attacker_type = _value(getattr(attacker_data, "energyType", None)) if attacker_data else None
    if weakness == attacker_type and weakness is not None:
        damage *= 2
    return damage


def _can_ko_target(state, target, card_data, attack_data):
    player = state.players[state.yourIndex]
    if _mawile_ready(player, card_data, attack_data):
        mawile_data = card_data.get(MEGA_MAWILE)
        for attack_id in mawile_data.attacks:
            attack = attack_data.get(attack_id)
            if attack and _attack_deficit(
                next(p for p in _pokemon(player) if p.id == MEGA_MAWILE), attack, card_data
            ) == 0 and _mawile_attack_damage(
                target, attack, card_data, 6 - _prizes_left(player)
            ) >= target.hp:
                return True
    return False


def _prizes_left(player):
    prizes = player.prize or []
    return prizes if isinstance(prizes, int) else len(prizes)


def _card_score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    card = _card_from_option(observation, option)
    card_id = getattr(card, "id", None)
    context = _context(observation)
    if context == SelectContext.SETUP_ACTIVE_POKEMON:
        if card_id == BUDEW:
            return 195
        return 180 if card_id == BELDUM else 115 if card_id == GENESECT_EX else 100
    if context in (SelectContext.TO_BENCH, SelectContext.SETUP_BENCH_POKEMON):
        if card_id == BUDEW:
            return 170 if state.turn <= 2 else 85
        if card_id == MEGA_MAWILE:
            return CONFIG["bench_mawile"]
        if card_id == GENESECT_EX:
            return 155 - 20 * _count(player, GENESECT_EX)
        if card_id == BELDUM:
            return 150 - 20 * _count(player, BELDUM)
        return 40
    if context == SelectContext.EVOLVES_TO:
        if card_id == METANG:
            return 240
        return 20
    if context == SelectContext.EVOLVES_FROM:
        if _TREE_STAGE_CARD_ID == METANG and card_id == BELDUM:
            return 240
        return 20
    if context == SelectContext.DISCARD:
        if card_id == METAL_ENERGY:
            return 75
        if card_id in (METANG, GENESECT_EX, MEGA_MAWILE, BELDUM):
            return 5
        return 50
    if context == SelectContext.TO_HAND:
        if card_id == MEGA_MAWILE and not _count(player, MEGA_MAWILE) and MEGA_MAWILE not in _hand_ids(player):
            return 250
        if card_id == METANG and not _count(player, METANG) and METANG not in _hand_ids(player):
            return 240
        if card_id == GENESECT_EX and not _count(player, GENESECT_EX) and GENESECT_EX not in _hand_ids(player):
            return 220
        if card_id == BELDUM and _count(player, BELDUM) + _hand_ids(player).count(BELDUM) < 2:
            return 210
        return 30
    if context in (SelectContext.ATTACH_TO, SelectContext.ATTACH_FROM):
        if card_id == METAL_ENERGY:
            return 260
        if card_id == MEGA_MAWILE:
            return 250
        return 5
    if context in (SelectContext.TO_ACTIVE, SelectContext.SWITCH):
        if _mawile_ready(player, card_data, attack_data) and card_id == MEGA_MAWILE:
            return 500
        if card_id in (BELDUM, METANG):
            return 180
        return 50
    if context == SelectContext.DAMAGE_COUNTER_ANY:
        return 0
    return 20


def _play_score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    card = _hand_card(state, option.index)
    card_id = getattr(card, "id", None)
    ids = _hand_ids(player)
    field = [item.id for item in _pokemon(player)]
    if card_id == POFFIN:
        return CONFIG["setup_search"] if _count(player, BELDUM) < 2 else 90
    if card_id == ULTRA_BALL:
        needs = not any(cid in field + ids for cid in (GENESECT_EX, MEGA_MAWILE))
        return CONFIG["setup_search"] - 5 if needs else 120
    if card_id == POKE_PAD:
        needs_metang = not any(cid == METANG for cid in field + ids)
        return CONFIG["stage_search"] if needs_metang else 115
    if card_id == GRAND_TREE:
        old_beldum = any(item.id == BELDUM and not item.appearThisTurn for item in _pokemon(player))
        return CONFIG["grand_tree"] if old_beldum and _count(player, METANG) == 0 else 60
    if card_id == CARMINE:
        return CONFIG["draw_supporter_early"] if state.turn <= 2 else 135
    if card_id == LILLIE:
        return CONFIG["draw_supporter_early"] if _prizes_left(player) == 6 or len(player.hand or []) <= 3 else 130
    if card_id == CRISPIN:
        return 155
    if card_id == DAWN:
        missing_mawile = _count(player, MEGA_MAWILE) + ids.count(MEGA_MAWILE) == 0
        missing_line = _count(player, BELDUM) + ids.count(BELDUM) < 2
        return 190 if missing_mawile or missing_line else 130
    if card_id == BOSS:
        if any(_can_ko_target(state, target, card_data, attack_data) for target in (opponent.bench or []) if target):
            return 185
        return 5
    if card_id == CRUSHING_HAMMER:
        return 130 if any(getattr(item, "energies", []) for item in _pokemon(opponent)) else 60
    if card_id == SWITCH:
        return 170 if _mawile_ready(player, card_data, attack_data) else 70
    if card_id == NIGHT_STRETCHER:
        return 125 if any(item.id in (BELDUM, METANG, GENESECT_EX, MEGA_MAWILE) for item in (player.discard or [])) else 90
    if card_id == MEGA_MAWILE:
        return 185 if not _count(player, MEGA_MAWILE) else 85
    if card_id == BUDEW:
        return 150 if not _count(player, BUDEW) else 70
    if card_id == GENESECT_EX:
        return 180 if _count(player, GENESECT_EX) < 2 else 90
    if card_id == METANG:
        return 175 if not _count(player, METANG) else 90
    if card_id == BELDUM:
        return 145 if _count(player, BELDUM) < 2 else 70
    return 75


def _ability_score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    source = _source(state, option)
    source_id = getattr(source, "id", None)
    ids = _hand_ids(player)
    field = [item.id for item in _pokemon(player)]
    if source_id == GENESECT_EX:
        return CONFIG["genesect_search"] if METANG not in ids or not _count(player, METANG) else 100
    if source_id == METANG:
        return CONFIG["metal_maker"]
    if source_id == GRAND_TREE:
        old_beldum = any(item.id == BELDUM and not item.appearThisTurn for item in _pokemon(player))
        return CONFIG["grand_tree"] if old_beldum and _count(player, METANG) == 0 else 5
    return 40


def _energy_target_score(target, energy_id, card_data, attack_data):
    if target is None:
        return -100
    if target.id == MEGA_MAWILE:
        current = len(getattr(target, "energies", []))
        return CONFIG["energy_attach"] + (110 if current < 3 else 0)
    if target.id == METANG:
        return 15
    if target.id == GENESECT_EX:
        return 10
    if target.id == BELDUM:
        return 20
    return 0


def _option_score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    context = _context(observation)
    kind = option.type
    if context == SelectContext.IS_FIRST and _STARTER_ID == BUDEW:
        return 100 if kind == OptionType.NO else 0
    if kind == OptionType.CARD:
        return _card_score(option, observation, card_data, attack_data)
    if kind == OptionType.ATTACH and context in (SelectContext.ATTACH_TO, SelectContext.ATTACH_FROM):
        target = _card_from_option(observation, option)
        return _energy_target_score(target, None, card_data, attack_data)
    if kind == OptionType.END:
        return -100
    if kind == OptionType.ABILITY:
        return _ability_score(option, observation, card_data, attack_data)
    if kind == OptionType.EVOLVE:
        card = _hand_card(state, option.index)
        target = _evolution_target(state, option)
        if getattr(card, "id", None) == METANG and getattr(target, "id", None) == BELDUM:
            return CONFIG["evolve_metang"]
        return 130
    if kind == OptionType.ATTACH:
        target = _target(state, option.inPlayArea, option.inPlayIndex, state.yourIndex)
        energy = _hand_card(state, option.index)
        energy_id = getattr(energy, "id", None)
        if target is None:
            return -100
        score = _energy_target_score(target, energy_id, card_data, attack_data)
        if energy_id == METAL_ENERGY and target.id == MEGA_MAWILE:
            score += max(0, 3 - len(getattr(target, "energies", []))) * 5
        return score
    if kind == OptionType.PLAY:
        return _play_score(option, observation, card_data, attack_data)
    if kind == OptionType.ATTACK:
        attack = attack_data.get(option.attackId)
        if attack is None:
            return CONFIG["attack"]
        active = opponent.active[0] if opponent.active else None
        attacker = player.active[0] if player.active else None
        damage = getattr(attack, "damage", 0)
        if attacker is not None and attacker.id == MEGA_MAWILE and active is not None:
            damage = _mawile_attack_damage(
                active, attack, card_data, 6 - _prizes_left(player)
            )
            if attack.name.lower() == "gobble down" and damage == 0:
                return -150
        score = CONFIG["attack"] + damage / 10
        if attack.name.lower() == "huge bite" and active is not None:
            if active.id == MEGA_ABOMASNOW and active.hp == active.maxHp:
                score += CONFIG["mawile_attack_ready"]
            elif active.id == MEGA_ABOMASNOW:
                score -= 80
        if attack.name.lower() == "protect charge":
            score += 30
        if attack.name.lower() == "itchy pollen":
            score += 180 if state.turn <= 2 else 40
        return score
    if kind == OptionType.RETREAT:
        return 20
    if kind == OptionType.YES:
        return 10
    if kind == OptionType.NO:
        return 0
    if kind == OptionType.NUMBER:
        return getattr(option, "number", 0)
    if context == SelectContext.DRAW_COUNT:
        return getattr(option, "number", 0)
    return 15


def agent(obs_dict):
    global _TREE_STAGE_CARD_ID, _STARTER_ID
    try:
        observation = to_observation_class(obs_dict)
        if observation.select is None:
            _TREE_STAGE_CARD_ID = None
            _STARTER_ID = None
            return _read_deck()
        card_data, attack_data = _metadata()
        options = observation.select.option
        context = _context(observation)
        ranked = sorted(
            range(len(options)),
            key=lambda index: _option_score(options[index], observation, card_data, attack_data),
            reverse=True,
        )
        selection = ranked[: observation.select.maxCount]
        if context == SelectContext.SETUP_ACTIVE_POKEMON and selection:
            starter = _card_from_option(observation, options[selection[0]])
            _STARTER_ID = getattr(starter, "id", None)
        if context == SelectContext.EVOLVES_TO and selection:
            card = _card_from_option(observation, options[selection[0]])
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
