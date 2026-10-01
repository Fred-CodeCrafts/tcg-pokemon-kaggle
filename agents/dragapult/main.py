from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from cg.api import AreaType, OptionType, SelectContext, all_attack, all_card_data, to_observation_class

DREEPY = 119
DRAKLOAK = 120
DRAGAPULT = 121
DUSKULL = 131
DUSCLOPS = 132
DUSKNOIR = 133
TATSUGIRI = 122
MUNKIDORI = 112
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
MEOWTH_EX = 1071
DUDUNSPARCE = 66
CRUSHING_HAMMER = 1120
POKE_PAD = 1152
UNFAIR_STAMP = 1080
SPECIAL_RED_CARD = 1413
ROSA = 1240
RISKY_RUINS = 1260
PRISM_ENERGY = 16
NEO_UPPER_ENERGY = 10
GRAND_TREE = 1249
LUCKY_HELMET = 1156
COMMUNITY_CENTER = 1242
JAMMING_TOWER = 1246
PHANTOM_DIVE = 154
FIRE = 2
PSYCHIC = 5

_CARD_DATA = None
_ATTACK_DATA = None
_PHANTOM_PENDING = False
_PHANTOM_COUNTERS_LEFT = 0
_PENDING_COUNTER_DAMAGE = 0
_STARTER_ID = None
_TREE_STAGE_CARD_ID = None

CONFIG = {
    "search_poffin": 200,
    "search_ultra_ball": 190,
    "search_poke_pad": 180,
    "evolve_dragapult": 175,
    "play_rare_candy": 180,
    "ability_drakloak": 170,
    "ability_supporter_search": 155,
    "play_supporter": 130,
    "attach_energy": 70,
    "energy_contribution_weight": 12,
    "energy_munkidori_priority": 35,
    "attack_last": 50,
    "phantom_dive_weight": 2.5,
    "jet_headbutt_weight": 0.25,
    "immediate_ko": 1000,
    "possible_ko": 260,
    "next_phantom_reach": 70,
    "dusknoir_reach": 55,
    "dusclops_reach": 35,
    "itchy_pollen_item_lock_bonus": 45,
    "setup_budew": 180,
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


def _context_id(observation):
    return _value(observation.select.context) if observation.select is not None else None


def _hand_card(state, index):
    hand = state.players[state.yourIndex].hand or []
    if isinstance(index, int) and 0 <= index < len(hand):
        return hand[index]
    return None


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
    return []


def _option_card(observation, option):
    area = getattr(option, "area", None)
    index = getattr(option, "index", None)
    player_index = getattr(option, "playerIndex", observation.current.yourIndex)
    if area is None or not isinstance(index, int):
        return None
    if _value(area) == AreaType.DECK:
        values = observation.select.deck or []
    else:
        values = _zone(observation.current, area, player_index)
    return values[index] if 0 <= index < len(values) else None


def _in_play_target(state, area, index, player_index):
    values = _zone(state, area, player_index)
    return values[index] if isinstance(index, int) and 0 <= index < len(values) else None


def _ability_source(state, option, player_index):
    return _in_play_target(
        state,
        getattr(option, "area", None),
        getattr(option, "index", None),
        player_index,
    )


def _play_target(state, option):
    return _in_play_target(
        state,
        getattr(option, "inPlayArea", None),
        getattr(option, "inPlayIndex", None),
        state.yourIndex,
    )


def _pokemon_on_board(player):
    return [pokemon for pokemon in (player.active or []) + (player.bench or []) if pokemon is not None]


def _prizes_left(player):
    prizes = getattr(player, "prize", []) or []
    if isinstance(prizes, int):
        return prizes
    return sum(prize is not None for prize in prizes)


def _prize_value(pokemon, card_data):
    data = card_data.get(getattr(pokemon, "id", None))
    if data is None:
        return 1
    if getattr(data, "megaEx", False):
        return 3
    if getattr(data, "ex", False):
        return 2
    return 1


def _energy_profile(pokemon, card_data):
    counts = Counter()
    flexible = 0
    total = 0
    energy_cards = getattr(pokemon, "energyCards", []) or []
    pokemon_data = card_data.get(getattr(pokemon, "id", None))
    if energy_cards:
        for energy_card in energy_cards:
            card_id = getattr(energy_card, "id", energy_card)
            data = card_data.get(card_id)
            if data is None:
                continue
            energy_type = _value(getattr(data, "energyType", None))
            if card_id == NEO_UPPER_ENERGY and getattr(pokemon_data, "stage2", False):
                flexible += 2
                total += 2
            elif card_id == PRISM_ENERGY and getattr(pokemon_data, "basic", False):
                flexible += 1
                total += 1
            elif energy_type is not None:
                counts[energy_type] += 1
                total += 1
    else:
        for energy in getattr(pokemon, "energies", []) or []:
            counts[_value(energy)] += 1
            total += 1
    return counts, flexible, total


def _attack_deficit(pokemon, attack, card_data, extra_type=None, extra_prism=False, extra_neo=False):
    required = Counter(_value(energy) for energy in getattr(attack, "energies", []))
    generic = required.pop(0, 0)
    counts, flexible, total = _energy_profile(pokemon, card_data)
    if extra_neo and getattr(card_data.get(pokemon.id), "stage2", False):
        flexible += 2
        total += 2
    elif extra_prism and getattr(card_data.get(pokemon.id), "basic", False):
        flexible += 1
        total += 1
    elif extra_type is not None:
        counts[extra_type] += 1
        total += 1
    filled_colored = sum(min(amount, counts[energy_type]) for energy_type, amount in required.items())
    missing_colored = sum(required.values()) - filled_colored
    used_flexible = min(flexible, missing_colored)
    missing_colored -= used_flexible
    filled_colored += used_flexible
    generic_missing = max(0, generic - max(0, total - filled_colored))
    return missing_colored + generic_missing


def _energy_contribution(pokemon, energy_type, is_prism, is_neo, card_data, attack_data):
    data = card_data.get(getattr(pokemon, "id", None))
    if data is None:
        return 0
    best = 0
    for attack_id in getattr(data, "attacks", []):
        attack = attack_data.get(attack_id)
        if attack is None:
            continue
        before = _attack_deficit(pokemon, attack, card_data)
        after = _attack_deficit(pokemon, attack, card_data, energy_type, is_prism, is_neo)
        if attack.name.lower() == "phantom dive":
            weight = CONFIG["phantom_dive_weight"]
        elif attack.name.lower() == "jet headbutt":
            weight = CONFIG["jet_headbutt_weight"]
        else:
            weight = 1
        best = max(best, (before - after) * weight)
    return best


def _hand_ids(player):
    return [card.id for card in (player.hand or []) if card is not None]


def _in_play_count(player, card_id):
    return sum(pokemon.id == card_id for pokemon in _pokemon_on_board(player))


def _has_supporter(player, card_data):
    return any(
        _value(getattr(card_data.get(card.id), "cardType", None)) == 3
        for card in (player.hand or [])
        if card is not None
    )


def _ready_attack_damage(player, card_data, attack_data):
    if not player.active or player.active[0] is None:
        return 0
    active = player.active[0]
    data = card_data.get(active.id)
    if data is None:
        return 0
    damages = []
    for attack_id in getattr(data, "attacks", []):
        attack = attack_data.get(attack_id)
        if attack is not None and _attack_deficit(active, attack, card_data) == 0:
            damages.append(getattr(attack, "damage", 0))
    return max(damages, default=0)


def _dusknoir_available(player):
    return any(pokemon.id == DUSKNOIR for pokemon in _pokemon_on_board(player))


def _profitable_cursed_blast(state, source_id, card_data):
    damage = 130 if source_id == DUSKNOIR else 50
    opponent = state.players[1 - state.yourIndex]
    prizes_remaining = _prizes_left(opponent)
    for pokemon in _pokemon_on_board(opponent):
        value = _prize_value(pokemon, card_data)
        if pokemon.hp <= damage and (value >= 2 or value >= prizes_remaining):
            return True
    return False


def _can_gust_for_ko(state, card_data, attack_data):
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    ready_damage = _ready_attack_damage(player, card_data, attack_data)
    prizes_remaining = _prizes_left(opponent)
    for pokemon in (opponent.bench or []):
        if pokemon is None:
            continue
        value = _prize_value(pokemon, card_data)
        if ready_damage and pokemon.hp <= ready_damage:
            return True
        if _dusknoir_available(player) and pokemon.hp <= 130 and (value >= 2 or value >= prizes_remaining):
            return True
    return False


def _target_for_gust_score(state, pokemon, card_data, attack_data):
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    value = _prize_value(pokemon, card_data)
    if pokemon.hp <= _ready_attack_damage(player, card_data, attack_data):
        return 400 + value * 150
    if _dusknoir_available(player) and pokemon.hp <= 130:
        if value >= 2 or value >= _prizes_left(opponent):
            return 300 + value * 120
    return 10 + value


def _rare_candy_viable(state):
    if state.turn <= 2:
        return False
    player = state.players[state.yourIndex]
    if DRAGAPULT not in _hand_ids(player):
        return False
    return any(
        pokemon.id == DREEPY and not getattr(pokemon, "appearThisTurn", False)
        for pokemon in _pokemon_on_board(player)
    )


def _lillie_is_live(state, player, card_data):
    if state.turn <= 2 and _prizes_left(player) == 6:
        return True
    hand = [card for card in (player.hand or []) if card is not None and card.id != LILLIE]
    if len(hand) <= 2:
        return True
    live_ids = {POFFIN, ULTRA_BALL, POKE_PAD, CRUSHING_HAMMER, NIGHT_STRETCHER, BOSS, CRISPIN}
    live = sum(
        card.id in live_ids
        or _value(getattr(card_data.get(card.id), "cardType", None)) in (0, 5)
        for card in hand
    )
    return live <= 1


def _search_priority(card_id, player, card_data):
    hand_ids = _hand_ids(player)
    field_ids = [pokemon.id for pokemon in _pokemon_on_board(player)]
    if card_id == POFFIN:
        setup_basics = sum(item_id == DREEPY for item_id in field_ids + hand_ids)
        return CONFIG["search_poffin"] if setup_basics < 2 else 115
    if card_id == ULTRA_BALL:
        available_ids = field_ids + hand_ids
        has_dreepy = DREEPY in available_ids
        has_drakloak = DRAKLOAK in available_ids
        has_dragapult = DRAGAPULT in available_ids
        missing_piece = (
            (has_drakloak and not has_dragapult)
            or (has_dreepy and not has_drakloak)
            or not has_dreepy
        )
        return CONFIG["search_ultra_ball"] if missing_piece else 135
    if card_id == POKE_PAD:
        return CONFIG["search_poke_pad"] if not _has_supporter(player, card_data) else 125
    return 0


def _play_score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    card = _hand_card(state, option.index)
    card_id = getattr(card, "id", None)
    if card_id in (POFFIN, ULTRA_BALL, POKE_PAD):
        return _search_priority(card_id, player, card_data)
    if card_id == RARE_CANDY:
        return CONFIG["play_rare_candy"] if _rare_candy_viable(state) else 5
    if card_id in (BOSS, PRIME_CATCHER):
        return 165 if _can_gust_for_ko(state, card_data, attack_data) else 5
    if card_id == LILLIE:
        return 175 if _lillie_is_live(state, player, card_data) else 10
    if card_id == CRUSHING_HAMMER:
        opposing_energy = sum(len(getattr(pokemon, "energies", [])) for pokemon in _pokemon_on_board(opponent))
        return 145 if opposing_energy else 65
    if card_id == UNFAIR_STAMP:
        return 150 if opponent.handCount >= 4 and _prizes_left(opponent) <= 3 else 95
    if card_id == SPECIAL_RED_CARD:
        return 140 if _prizes_left(opponent) <= 3 else 45
    if card_id == NIGHT_STRETCHER:
        needed_ids = (DREEPY, DRAKLOAK, DRAGAPULT, FIRE, PSYCHIC)
        return 125 if any(card.id in needed_ids for card in (player.discard or [])) else 95
    if card_id == ROSA:
        has_stage2 = any(pokemon.id == DRAGAPULT for pokemon in _pokemon_on_board(player))
        return 140 if has_stage2 and _prizes_left(player) > _prizes_left(opponent) else 25
    if card_id == GRAND_TREE:
        has_old_dreepy = any(
            pokemon.id == DREEPY and not pokemon.appearThisTurn
            for pokemon in _pokemon_on_board(player)
        )
        return 195 if state.turn > 2 and has_old_dreepy else 75
    if card_id in (CRISPIN, DAWN):
        return 140
    if card_id == RISKY_RUINS:
        return 65
    if card_id in (COMMUNITY_CENTER, JAMMING_TOWER):
        return 55
    data = card_data.get(card_id)
    card_type = _value(getattr(data, "cardType", None))
    if card_type == 0:
        return 125 if state.turn <= 4 else 90
    if card_type == 1:
        return 105
    if card_type == 2:
        return 60
    if card_type == 3:
        return CONFIG["play_supporter"]
    if card_type == 4:
        return 65
    return 40


def _ability_score(option, observation, card_data):
    state = observation.current
    player = state.players[state.yourIndex]
    source = _ability_source(state, option, state.yourIndex)
    source_id = getattr(source, "id", None)
    if source_id == DRAKLOAK:
        return CONFIG["ability_drakloak"]
    if source_id == GRAND_TREE:
        eligible = any(
            pokemon.id == DREEPY and not pokemon.appearThisTurn
            for pokemon in _pokemon_on_board(player)
        )
        return 190 if eligible else 5
    if source_id in (TATSUGIRI, MEOWTH_EX):
        return CONFIG["ability_supporter_search"] if not _has_supporter(player, card_data) else 70
    if source_id == DUDUNSPARCE:
        return 155 if len(player.hand or []) <= 4 else 95
    if source_id == MUNKIDORI:
        return 150 if any(pokemon.hp < pokemon.maxHp for pokemon in _pokemon_on_board(player)) else 50
    if source_id in (DUSKNOIR, DUSCLOPS):
        return 175 if _profitable_cursed_blast(state, source_id, card_data) else -500
    if source_id == FEZANDIPITI:
        return 145
    return 70


def _score_energy_attach(option, observation, card_data, attack_data):
    state = observation.current
    target = _play_target(state, option)
    energy_card = _hand_card(state, option.index)
    if target is None or energy_card is None:
        return 0
    energy_data = card_data.get(energy_card.id)
    energy_type = _value(getattr(energy_data, "energyType", None))
    is_prism = energy_card.id == PRISM_ENERGY
    is_neo = energy_card.id == NEO_UPPER_ENERGY
    if (
        energy_type == 7
        and target.id in (DREEPY, DRAKLOAK, DRAGAPULT)
        and not _in_play_count(state.players[state.yourIndex], MUNKIDORI)
        and MUNKIDORI in _hand_ids(state.players[state.yourIndex])
    ):
        return -1001
    contribution = _energy_contribution(target, energy_type, is_prism, is_neo, card_data, attack_data)
    score = CONFIG["attach_energy"] + CONFIG["energy_contribution_weight"] * contribution
    if target.id == MUNKIDORI and energy_type == 7 and not any(
        _value(energy) == 7 for energy in getattr(target, "energies", [])
    ):
        score += CONFIG["energy_munkidori_priority"]
    if target.id in (BUDEW, DUSKULL, TATSUGIRI):
        return -1001
    if contribution <= 0 and not (target.id == MUNKIDORI and energy_type == 7):
        return -1001
    if target.id in (DRAGAPULT, DRAKLOAK, DREEPY):
        score += 25
    elif target.id != MUNKIDORI:
        score = -900
    if target.id == DUDUNSPARCE:
        score -= 30
    return score


def _counter_target_score(option, observation, card_data):
    state = observation.current
    target = _option_card(observation, option)
    if target is None:
        return -1000
    opponent = state.players[1 - state.yourIndex]
    player = state.players[state.yourIndex]
    value = _prize_value(target, card_data)
    hp_after = target.hp - 10
    counters_left = _PHANTOM_COUNTERS_LEFT if _PHANTOM_PENDING else 6
    prizes_left = _prizes_left(opponent)
    score = 10 + value * 5
    if hp_after <= 0:
        score += CONFIG["immediate_ko"] + value * 250
        if value >= prizes_left:
            score += 1000
    elif (hp_after + 9) // 10 <= counters_left - 1:
        score += CONFIG["possible_ko"] + value * 90
    if hp_after <= 60:
        score += CONFIG["next_phantom_reach"] * value
    if hp_after <= 130 and _dusknoir_available(player):
        score += CONFIG["dusknoir_reach"] * value
    if hp_after <= 50 and any(pokemon.id == DUSCLOPS for pokemon in _pokemon_on_board(player)):
        score += CONFIG["dusclops_reach"] * value
    return score


def _selection_card_score(option, observation, card_data, attack_data):
    state = observation.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    context = _context_id(observation)
    card = _option_card(observation, option)
    card_id = getattr(card, "id", None)
    if context == SelectContext.EVOLVES_TO:
        if card_id == DRAKLOAK and _in_play_count(player, DREEPY):
            return 220
        if card_id == DRAGAPULT and _in_play_count(player, DRAKLOAK):
            return 230
        if card_id == DUDUNSPARCE and _in_play_count(player, 65):
            return 110
        return 10
    if context == SelectContext.EVOLVES_FROM:
        if card is not None and _TREE_STAGE_CARD_ID is not None:
            chosen_data = card_data.get(_TREE_STAGE_CARD_ID)
            evolves_from = getattr(chosen_data, "evolvesFrom", None)
            if evolves_from == "Dreepy" and card_id == DREEPY:
                return 230
            if evolves_from == "Drakloak" and card_id == DRAKLOAK:
                return 240
            if evolves_from == "Dunsparce" and card_id == 65:
                return 180
    if context == SelectContext.DAMAGE_COUNTER_ANY:
        return _counter_target_score(option, observation, card_data)
    if context == SelectContext.DAMAGE_COUNTER:
        if card is None:
            return -100
        damage = _PENDING_COUNTER_DAMAGE or 10
        value = _prize_value(card, card_data)
        score = 100 + value * 40
        if card.hp <= damage:
            score += CONFIG["immediate_ko"] + value * 250
            if value >= _prizes_left(opponent):
                score += 1000
        return score
    if context in (SelectContext.TO_ACTIVE, SelectContext.SWITCH) and card is not None:
        return _target_for_gust_score(state, card, card_data, attack_data)
    if context in (SelectContext.TO_BENCH, SelectContext.SETUP_BENCH_POKEMON):
        if card_id == DREEPY:
            return 150 - 25 * _in_play_count(player, DREEPY)
        if card_id == BUDEW and state.turn <= 2:
            return 125
        if card_id == MUNKIDORI and not _in_play_count(player, MUNKIDORI):
            return 115
        if card_id in (DUSKULL, TATSUGIRI) and not _in_play_count(player, card_id):
            return 105
        return 50
    if context == SelectContext.SETUP_ACTIVE_POKEMON:
        if card_id == BUDEW:
            return CONFIG["setup_budew"]
        if card_id == DREEPY:
            return 165
        return 70
    if context == SelectContext.TO_HAND and card is not None:
        if card_id == DRAKLOAK and _in_play_count(player, DREEPY):
            return 160
        if card_id == DREEPY and _in_play_count(player, DREEPY) < 2:
            return 145
        if card_id == DRAGAPULT and _in_play_count(player, DRAKLOAK):
            return 155
        if card_id in (TATSUGIRI, MUNKIDORI, MEOWTH_EX) and not _in_play_count(player, card_id):
            return 100
        if _value(getattr(card_data.get(card_id), "cardType", None)) == 3:
            return 120
        return 30
    if context == SelectContext.TO_DECK_BOTTOM and card is not None:
        if card_id in (DREEPY, DRAKLOAK, DRAGAPULT, POFFIN, ULTRA_BALL):
            return 5
        return 90
    if context == SelectContext.DISCARD and card is not None:
        duplicates = _hand_ids(player).count(card_id)
        if card_id in (DREEPY, DRAKLOAK, DRAGAPULT, FIRE, PSYCHIC):
            return 5 + duplicates
        if card_id in (BOSS, CRISPIN, LILLIE, POFFIN, ULTRA_BALL):
            return 10 + duplicates
        return 70 + duplicates * 20
    return 20


def _score(option, observation, card_data, attack_data):
    state = observation.current
    context = _context_id(observation)
    kind = option.type
    if context == SelectContext.IS_FIRST:
        if kind == OptionType.NO:
            return 100 if _STARTER_ID == BUDEW else 0
        if kind == OptionType.YES:
            return 0 if _STARTER_ID == BUDEW else 10
    if kind == OptionType.CARD:
        return _selection_card_score(option, observation, card_data, attack_data)
    if kind == OptionType.END:
        return -1000
    if kind == OptionType.ATTACK:
        attack = attack_data.get(option.attackId)
        damage = getattr(attack, "damage", 0) if attack else 0
        opponent = state.players[1 - state.yourIndex]
        active = opponent.active[0] if opponent.active else None
        score = CONFIG["attack_last"] + damage / 10
        if active is not None and damage >= active.hp > 0:
            score += 80
        if attack is not None and attack.name.lower() == "phantom dive":
            score += 15
        if attack is not None and attack.name.lower() == "itchy pollen":
            score += CONFIG["itchy_pollen_item_lock_bonus"]
        return score
    if kind == OptionType.EVOLVE:
        card = _hand_card(state, option.index)
        target = _play_target(state, option)
        card_id = getattr(card, "id", None)
        if card_id == DRAGAPULT and target is not None and target.id in (DREEPY, DRAKLOAK):
            return CONFIG["evolve_dragapult"]
        if card_id == DRAKLOAK and target is not None and target.id == DREEPY:
            return CONFIG["evolve_dragapult"] - 5
        return 145
    if kind == OptionType.ABILITY:
        return _ability_score(option, observation, card_data)
    if kind == OptionType.ATTACH:
        return _score_energy_attach(option, observation, card_data, attack_data)
    if kind == OptionType.PLAY:
        return _play_score(option, observation, card_data, attack_data)
    if kind == OptionType.NUMBER:
        return getattr(option, "number", 0)
    if kind == OptionType.YES:
        return 10
    if kind == OptionType.NO:
        return 0
    if kind == OptionType.RETREAT:
        return 15
    if context == SelectContext.DRAW_COUNT:
        return getattr(option, "number", 0)
    return 5


def _agent_impl(obs_dict):
    global _PHANTOM_PENDING, _PHANTOM_COUNTERS_LEFT, _PENDING_COUNTER_DAMAGE, _STARTER_ID
    global _TREE_STAGE_CARD_ID
    observation = to_observation_class(obs_dict)
    if observation.select is None:
        _PHANTOM_PENDING = False
        _PHANTOM_COUNTERS_LEFT = 0
        _PENDING_COUNTER_DAMAGE = 0
        _STARTER_ID = None
        _TREE_STAGE_CARD_ID = None
        return _read_deck()
    card_data, attack_data = _metadata()
    options = observation.select.option
    ranked = sorted(
        range(len(options)),
        key=lambda index: _score(options[index], observation, card_data, attack_data),
        reverse=True,
    )
    selection = ranked[: observation.select.maxCount]
    context = _context_id(observation)
    if context == SelectContext.SETUP_ACTIVE_POKEMON and selection:
        starter = _option_card(observation, options[selection[0]])
        _STARTER_ID = getattr(starter, "id", None)
    elif context == SelectContext.EVOLVES_TO and selection:
        selected_card = _option_card(observation, options[selection[0]])
        _TREE_STAGE_CARD_ID = getattr(selected_card, "id", None)
    elif context == SelectContext.EVOLVES_FROM:
        _TREE_STAGE_CARD_ID = None
    elif context == SelectContext.MAIN and selection:
        selected = options[selection[0]]
        if selected.type == OptionType.ATTACK:
            attack = attack_data.get(selected.attackId)
            if attack is not None and attack.name.lower() == "phantom dive":
                _PHANTOM_PENDING = True
                _PHANTOM_COUNTERS_LEFT = 6
        elif selected.type == OptionType.ABILITY:
            source = _ability_source(observation.current, selected, observation.current.yourIndex)
            source_id = getattr(source, "id", None)
            if source_id == GRAND_TREE:
                _TREE_STAGE_CARD_ID = None
            if source_id == DUSKNOIR:
                _PENDING_COUNTER_DAMAGE = 130
            elif source_id == DUSCLOPS:
                _PENDING_COUNTER_DAMAGE = 50
    elif context == SelectContext.DAMAGE_COUNTER_ANY and _PHANTOM_PENDING:
        _PHANTOM_COUNTERS_LEFT = max(0, _PHANTOM_COUNTERS_LEFT - len(selection))
        if _PHANTOM_COUNTERS_LEFT == 0:
            _PHANTOM_PENDING = False
    elif context == SelectContext.DAMAGE_COUNTER and _PENDING_COUNTER_DAMAGE:
        _PENDING_COUNTER_DAMAGE = 0
    return selection


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
