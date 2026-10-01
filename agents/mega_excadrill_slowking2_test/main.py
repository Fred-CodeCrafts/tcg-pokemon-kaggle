from __future__ import annotations

import csv
from pathlib import Path

from cg.api import AreaType, OptionType, SelectContext, all_attack, all_card_data, to_observation_class

DRILBUR = 1387
MEGA_EXCADRILL = 1406
BELDUM = 85
METANG = 86
GENESECT_EX = 547
METAL_ENERGY = 8
SLOWPOKE = 162
SLOWKING = 163
PSYCHIC_ENERGY = 5

POFFIN = 1086
ULTRA_BALL = 1121
POKE_PAD = 1152
CARMINE = 1192
LILLIE = 1227
BOSS = 1182
SWITCH = 1123
NIGHT_STRETCHER = 1097
GRAND_TREE = 1249
PRIME_CATCHER = 1088

FALLBACK_DECK = (
    (DRILBUR,) * 4
    + (MEGA_EXCADRILL,) * 4
    + (BELDUM,) * 4
    + (METANG,) * 4
    + (GENESECT_EX,) * 4
    + (POFFIN,) * 4
    + (ULTRA_BALL,) * 4
    + (POKE_PAD,) * 4
    + (CARMINE,) * 2
    + (LILLIE,) * 3
    + (BOSS,) * 2
    + (SWITCH, NIGHT_STRETCHER, PRIME_CATCHER)
    + (METAL_ENERGY,) * 18
)

CONFIG = {
    "setup_search": 205,
    "find_evolution": 195,
    "evolve": 190,
    "genesect_signal": 205,
    "metal_maker": 215,
    "grand_tree": 195,
    "draw_early": 170,
    "attach_metal": 150,
    "attack_base": 45,
    "attack_damage": 0.35,
    "ko_bonus": 900,
    "prize_bonus": 250,
}

_CARD_DATA = None
_ATTACK_DATA = None
_TREE_STAGE_CARD_ID = None


def _read_deck():
    for path in (Path(__file__).with_name("deck.csv"), Path("deck.csv")):
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


def _context(obs):
    return _value(obs.select.context) if obs.select is not None else None


def _zone(state, area, player_index):
    if not isinstance(player_index, int) or not 0 <= player_index < len(state.players):
        return []
    player = state.players[player_index]
    area = _value(area)
    if area == AreaType.HAND:
        return player.hand or []
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


def _selected_card(obs, option):
    area = getattr(option, "area", None)
    index = getattr(option, "index", None)
    owner = getattr(option, "playerIndex", obs.current.yourIndex)
    if area is None or not isinstance(index, int):
        return None
    if _value(area) == AreaType.DECK:
        values = obs.select.deck or []
    else:
        values = _zone(obs.current, area, owner)
    return values[index] if 0 <= index < len(values) else None


def _hand_card(state, index):
    hand = state.players[state.yourIndex].hand or []
    return hand[index] if isinstance(index, int) and 0 <= index < len(hand) else None


def _target(state, area, index, owner):
    zone = _zone(state, area, owner)
    return zone[index] if isinstance(index, int) and 0 <= index < len(zone) else None


def _board(player):
    return [pokemon for pokemon in (player.active or []) + (player.bench or []) if pokemon is not None]


def _count(player, card_id):
    return sum(pokemon.id == card_id for pokemon in _board(player))


def _hand_ids(player):
    return [card.id for card in (player.hand or []) if card is not None]


def _attack_deficit(pokemon, attack, card_data):
    required = {}
    for energy in getattr(attack, "energies", []):
        energy_type = _value(energy)
        required[energy_type] = required.get(energy_type, 0) + 1
    generic = required.pop(0, 0)
    attached = {}
    total = 0
    energy_cards = getattr(pokemon, "energyCards", []) or []
    if energy_cards:
        for energy_card in energy_cards:
            data = card_data.get(energy_card.id)
            if data is None:
                continue
            energy_type = _value(data.energyType)
            attached[energy_type] = attached.get(energy_type, 0) + 1
            total += 1
    else:
        for energy in getattr(pokemon, "energies", []) or []:
            energy_type = _value(energy)
            attached[energy_type] = attached.get(energy_type, 0) + 1
            total += 1
    colored_used = sum(min(amount, attached.get(kind, 0)) for kind, amount in required.items())
    colored_missing = sum(required.values()) - colored_used
    generic_missing = max(0, generic - max(0, total - colored_used))
    return colored_missing + generic_missing


def _effective_damage(attacker, defender, attack, card_data):
    damage = getattr(attack, "damage", 0)
    if attack.name.lower() == "maximum drilling" and len(getattr(attacker, "energies", [])) >= 5:
        damage += 130
    attacker_data = card_data.get(attacker.id)
    defender_data = card_data.get(defender.id)
    attacker_type = _value(getattr(attacker_data, "energyType", None)) if attacker_data else None
    weakness = _value(getattr(defender_data, "weakness", None)) if defender_data else None
    resistance = _value(getattr(defender_data, "resistance", None)) if defender_data else None
    if weakness is not None and weakness == attacker_type:
        damage *= 2
    elif resistance is not None and resistance == attacker_type:
        damage = max(0, damage - 30)
    return damage


def _prizes(pokemon, card_data):
    data = card_data.get(pokemon.id)
    if data is None:
        return 1
    return 3 if data.megaEx else 2 if data.ex else 1


def _prizes_left(player):
    prizes = player.prize or []
    return prizes if isinstance(prizes, int) else len(prizes)


def _slowking_ready(player, card_data, attack_data):
    data = card_data.get(SLOWKING)
    if data is None:
        return False
    for pokemon in _board(player):
        if pokemon.id != SLOWKING:
            continue
        for attack_id in data.attacks:
            attack = attack_data.get(attack_id)
            if attack and attack.name.lower() == "seek inspiration":
                return _attack_deficit(pokemon, attack, card_data) == 0
    return False


def _is_old_base(player, card_id):
    return any(pokemon.id == card_id and not pokemon.appearThisTurn for pokemon in _board(player))


def _card_score(option, obs, card_data, attack_data):
    state = obs.current
    player = state.players[state.yourIndex]
    card = _selected_card(obs, option)
    card_id = getattr(card, "id", None)
    context = _context(obs)
    hand_ids = _hand_ids(player)
    if context == SelectContext.SETUP_ACTIVE_POKEMON:
        return 190 if card_id == DRILBUR else 155 if card_id == BELDUM else 120 if card_id == SLOWPOKE else 130
    if context in (SelectContext.TO_BENCH, SelectContext.SETUP_BENCH_POKEMON):
        if card_id == GENESECT_EX:
            return 175 - 25 * _count(player, GENESECT_EX)
        if card_id == DRILBUR:
            return 165 - 20 * _count(player, DRILBUR)
        if card_id == BELDUM:
            return 155 - 20 * _count(player, BELDUM)
        if card_id == SLOWPOKE and not _count(player, SLOWPOKE):
            return 160 if SLOWKING in _hand_ids(player) else 120
        return 40
    if context == SelectContext.TO_HAND:
        if card_id == SLOWKING and _count(player, SLOWPOKE) and SLOWKING not in _hand_ids(player):
            return 235
        if card_id == SLOWPOKE and not _count(player, SLOWPOKE) and SLOWPOKE not in _hand_ids(player):
            return 165
        if card_id == MEGA_EXCADRILL and _count(player, DRILBUR) and MEGA_EXCADRILL not in hand_ids:
            return 250
        if card_id == METANG and _count(player, BELDUM) and METANG not in hand_ids:
            return 240
        if card_id == GENESECT_EX and not _count(player, GENESECT_EX) and GENESECT_EX not in hand_ids:
            return 230
        if card_id == DRILBUR and _count(player, DRILBUR) < 2:
            return 210
        if card_id == BELDUM and _count(player, BELDUM) < 2:
            return 200
        return 25
    if context == SelectContext.EVOLVES_TO:
        if card_id == MEGA_EXCADRILL:
            return 250
        if card_id == METANG:
            return 240
        if card_id == SLOWKING:
            return 230
        return 10
    if context == SelectContext.EVOLVES_FROM:
        if _TREE_STAGE_CARD_ID == MEGA_EXCADRILL and card_id == DRILBUR:
            return 250
        if _TREE_STAGE_CARD_ID == METANG and card_id == BELDUM:
            return 240
        if _TREE_STAGE_CARD_ID == SLOWKING and card_id == SLOWPOKE:
            return 230
        return 10
    if context == SelectContext.ATTACH_TO:
        if card_id == MEGA_EXCADRILL:
            return 240
        if card_id == METANG:
            return 80
        return 10
    if context == SelectContext.DISCARD:
        if card_id in (MEGA_EXCADRILL, METANG, GENESECT_EX, DRILBUR, BELDUM):
            return 5
        if card_id == METAL_ENERGY:
            return 25
        return 60
    if context in (SelectContext.TO_ACTIVE, SelectContext.SWITCH):
        owner = getattr(option, "playerIndex", state.yourIndex)
        if owner != state.yourIndex:
            if card is not None and _can_ko_with_active(state, card, obs, card_data, attack_data):
                return 1200 + _prizes(card, card_data) * 100
            return 20 + (_prizes(card, card_data) if card is not None else 0)
        if card_id == MEGA_EXCADRILL and len(getattr(card, "energies", [])) >= 3:
            return 500
        if card_id == SLOWKING and _slowking_ready(player, card_data, _metadata()[1]):
            return 420
        if card_id == DRILBUR:
            return 150
        if card_id in (BELDUM, METANG):
            return 100
        return 40
    return 15


def _play_score(option, obs):
    state = obs.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    card = _hand_card(state, option.index)
    card_id = getattr(card, "id", None)
    hand_ids = _hand_ids(player)
    field_ids = [pokemon.id for pokemon in _board(player)]
    if card_id == POFFIN:
        return 205 if _count(player, DRILBUR) + _count(player, BELDUM) < 3 else 90
    if card_id == ULTRA_BALL:
        available = field_ids + hand_ids
        missing = GENESECT_EX not in available or (
            MEGA_EXCADRILL not in available and DRILBUR in available
        )
        return 195 if missing else 125
    if card_id == POKE_PAD:
        if METANG not in field_ids + hand_ids:
            return 190
        if SLOWPOKE in field_ids + hand_ids and SLOWKING not in field_ids + hand_ids:
            return 185
        return 115
    if card_id == GRAND_TREE:
        eligible = _is_old_base(player, DRILBUR) or _is_old_base(player, BELDUM)
        return 200 if eligible else 60
    if card_id == CARMINE:
        return 180 if state.turn <= 2 and state.firstPlayer == state.yourIndex else 55
    if card_id == LILLIE:
        return 175 if _prizes_left(player) == 6 or len(player.hand or []) <= 3 else 120
    if card_id == BOSS:
        opponent = state.players[1 - state.yourIndex]
        for target in (opponent.bench or []):
            if target is not None and _can_ko_with_active(state, target, obs, _metadata()[0], _metadata()[1]):
                return 185
        return 30
    if card_id == PRIME_CATCHER:
        if any(
            target is not None and _can_ko_with_active(state, target, obs, _metadata()[0], _metadata()[1])
            for target in (opponent.bench or [])
        ):
            return 215
        return 65
    if card_id == NIGHT_STRETCHER:
        return 130 if any(item.id in (DRILBUR, MEGA_EXCADRILL, BELDUM, METANG, GENESECT_EX) for item in (player.discard or [])) else 85
    if card_id in (DRILBUR, BELDUM, METANG, MEGA_EXCADRILL, GENESECT_EX):
        return 180 if not _count(player, card_id) else 80
    if card_id == SLOWPOKE:
        return 150 if not _count(player, SLOWPOKE) else 50
    if card_id == SLOWKING:
        return 175 if _count(player, SLOWPOKE) else 70
    if _metadata()[0].get(card_id) and _value(_metadata()[0][card_id].cardType) == 3:
        return 130
    return 70


def _can_ko_with_active(state, target, obs, card_data, attack_data):
    player = state.players[state.yourIndex]
    if not player.active or player.active[0] is None:
        return False
    attacker = player.active[0]
    data = card_data.get(attacker.id)
    if data is None:
        return False
    for attack_id in data.attacks:
        attack = attack_data.get(attack_id)
        if attack and _attack_deficit(attacker, attack, card_data) == 0:
            if _effective_damage(attacker, target, attack, card_data) >= target.hp:
                return True
    return False


def _ability_score(option, obs):
    state = obs.current
    player = state.players[state.yourIndex]
    source = _target(state, option.area, option.index, state.yourIndex)
    source_id = getattr(source, "id", None)
    hand_ids = _hand_ids(player)
    field_ids = [pokemon.id for pokemon in _board(player)]
    if source_id == GENESECT_EX:
        available = hand_ids + field_ids
        needs_excadrill = MEGA_EXCADRILL not in available and DRILBUR in available
        needs_metang = METANG not in available and BELDUM in available
        missing_evolution = needs_excadrill or needs_metang
        return 210 if missing_evolution else 110
    if source_id == METANG:
        return 220
    if source_id == GRAND_TREE:
        return 200 if _is_old_base(player, DRILBUR) or _is_old_base(player, BELDUM) else 5
    return 40


def _attach_score(option, obs):
    state = obs.current
    target = _target(state, option.inPlayArea, option.inPlayIndex, state.yourIndex)
    energy = _hand_card(state, option.index)
    if target is None or energy is None:
        return -100
    attached_types = [_value(item) for item in getattr(target, "energies", [])]
    if energy.id == PSYCHIC_ENERGY and target.id in (SLOWPOKE, SLOWKING):
        return 210 if PSYCHIC_ENERGY not in attached_types else 30
    if energy.id == METAL_ENERGY and target.id == SLOWKING:
        if len(attached_types) == 1 and PSYCHIC_ENERGY in attached_types:
            return 260
        return 20
    if energy.id == METAL_ENERGY and target.id == SLOWPOKE:
        if len(attached_types) == 1 and PSYCHIC_ENERGY in attached_types and SLOWKING in _hand_ids(state.players[state.yourIndex]):
            return 200
        return 10
    if energy.id != METAL_ENERGY:
        return -100
    count = len(getattr(target, "energies", []))
    if target.id == MEGA_EXCADRILL:
        return 180 + max(0, 3 - count) * 30
    if target.id == DRILBUR and count == 0 and not _count(state.players[state.yourIndex], MEGA_EXCADRILL):
        return 170
    if target.id == METANG:
        return 60
    return 10


def _score(option, obs, card_data, attack_data):
    state = obs.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    context = _context(obs)
    kind = option.type
    if kind == OptionType.CARD:
        return _card_score(option, obs, card_data, attack_data)
    if kind == OptionType.END:
        return -100
    if kind == OptionType.ABILITY:
        return _ability_score(option, obs)
    if kind == OptionType.EVOLVE:
        card = _hand_card(state, option.index)
        target = _target(state, option.inPlayArea, option.inPlayIndex, state.yourIndex)
        if getattr(card, "id", None) == MEGA_EXCADRILL and getattr(target, "id", None) == DRILBUR:
            return 190
        if getattr(card, "id", None) == METANG and getattr(target, "id", None) == BELDUM:
            return 185
        if getattr(card, "id", None) == SLOWKING and getattr(target, "id", None) == SLOWPOKE:
            return 180
        return 100
    if kind == OptionType.ATTACH:
        return _attach_score(option, obs)
    if kind == OptionType.PLAY:
        return _play_score(option, obs)
    if kind == OptionType.ATTACK:
        attack = attack_data.get(option.attackId)
        if attack is None:
            return CONFIG["attack_base"]
        attacker = player.active[0] if player.active else None
        defender = opponent.active[0] if opponent.active else None
        if attacker is None or defender is None:
            return CONFIG["attack_base"]
        damage = _effective_damage(attacker, defender, attack, card_data)
        score = CONFIG["attack_base"] + damage * CONFIG["attack_damage"]
        if attack.name.lower() == "seek inspiration":
            score += 85
        if damage >= defender.hp:
            prize_value = _prizes(defender, card_data)
            score += CONFIG["ko_bonus"] + prize_value * CONFIG["prize_bonus"]
            if prize_value >= _prizes_left(opponent):
                score += 1000
        if attack.name.lower() == "call for family":
            missing_basics = 4 - sum(_count(player, card_id) for card_id in (DRILBUR, BELDUM, GENESECT_EX))
            if state.turn <= 2 and missing_basics > 0:
                score += 180
        if attack.name.lower() == "undermine":
            score += 15
        return score
    if kind == OptionType.NUMBER:
        return getattr(option, "number", 0)
    if kind == OptionType.YES:
        return 10
    if kind == OptionType.NO:
        return 0
    if kind == OptionType.RETREAT:
        return 20
    if context == SelectContext.DRAW_COUNT:
        return getattr(option, "number", 0)
    return 15


def agent(obs_dict):
    global _TREE_STAGE_CARD_ID
    try:
        obs = to_observation_class(obs_dict)
        if obs.select is None:
            _TREE_STAGE_CARD_ID = None
            return _read_deck()
        card_data, attack_data = _metadata()
        options = obs.select.option
        context = _context(obs)
        ranked = sorted(
            range(len(options)),
            key=lambda index: _score(options[index], obs, card_data, attack_data),
            reverse=True,
        )
        selection = ranked[:obs.select.maxCount]
        if context == SelectContext.EVOLVES_TO and selection:
            card = _selected_card(obs, options[selection[0]])
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
        minimum = select.get("minCount", 0)
        maximum = select.get("maxCount", 0)
        options = select.get("option") or []
        if isinstance(minimum, int) and isinstance(maximum, int) and 0 <= minimum <= maximum <= len(options):
            return list(range(maximum))
        return []
