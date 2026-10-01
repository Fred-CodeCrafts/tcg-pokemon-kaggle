from __future__ import annotations

import csv
from pathlib import Path

from cg.api import AreaType, OptionType, SelectContext, all_attack, all_card_data, to_observation_class

MAKUHITA = 673
HARIYAMA = 674
LUNATONE = 675
SOLROCK = 676
RIOLU = 677
MEGA_LUCARIO = 678
FIGHTING_ENERGY = 6
DUSK_BALL = 1102
SWITCH = 1123
POWER_PRO = 1141
FIGHTING_GONG = 1142
POKE_PAD = 1152
HERO_CAPE = 1159
BOSS = 1182
CARMINE = 1192
LILLIE = 1227
GRAVITY_MOUNTAIN = 1252

_CARD_DATA = None
_ATTACK_DATA = None


def _read_deck():
    with Path(__file__).with_name("deck.csv").open(newline="") as deck_file:
        return [int(row[0]) for row in csv.reader(deck_file) if row]


def _metadata():
    global _CARD_DATA, _ATTACK_DATA
    if _CARD_DATA is None:
        _CARD_DATA = {card.cardId: card for card in all_card_data()}
        _ATTACK_DATA = {attack.attackId: attack for attack in all_attack()}
    return _CARD_DATA, _ATTACK_DATA


def _context(obs):
    return getattr(obs.select.context, "value", obs.select.context)


def _zone(state, area, player_index):
    if player_index not in (0, 1):
        return []
    player = state.players[player_index]
    area = getattr(area, "value", area)
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
    if area == AreaType.LOOKING:
        return state.looking or []
    return []


def _selected_card(obs, option):
    area = getattr(option, "area", None)
    index = getattr(option, "index", None)
    owner = getattr(option, "playerIndex", obs.current.yourIndex)
    if area is None or not isinstance(index, int):
        return None
    values = obs.select.deck or [] if getattr(area, "value", area) == AreaType.DECK else _zone(obs.current, area, owner)
    return values[index] if 0 <= index < len(values) else None


def _hand_card(state, index):
    hand = state.players[state.yourIndex].hand or []
    return hand[index] if isinstance(index, int) and 0 <= index < len(hand) else None


def _target(state, option, player_index=None):
    owner = state.yourIndex if player_index is None else player_index
    values = _zone(state, option.inPlayArea, owner)
    index = getattr(option, "inPlayIndex", None)
    return values[index] if isinstance(index, int) and 0 <= index < len(values) else None


def _board(player):
    return [card for card in (player.active or []) + (player.bench or []) if card is not None]


def _count(player, card_id):
    return sum(card.id == card_id for card in _board(player))


def _prizes(pokemon, card_data):
    data = card_data.get(pokemon.id)
    return 3 if getattr(data, "megaEx", False) else 2 if getattr(data, "ex", False) else 1


def _effective_damage(attacker, attack, defender, card_data):
    damage = getattr(attack, "damage", 0)
    if attacker.id == MEGA_LUCARIO and attack.name.lower() == "mega brave":
        damage += 30
    if attack.name.lower() == "cosmic beam":
        damage = 70
    attack_data = card_data.get(attacker.id)
    defender_data = card_data.get(defender.id)
    attack_type = getattr(attack_data, "energyType", None)
    weakness = getattr(defender_data, "weakness", None)
    resistance = getattr(defender_data, "resistance", None)
    attack_type = getattr(attack_type, "value", attack_type)
    weakness = getattr(weakness, "value", weakness)
    resistance = getattr(resistance, "value", resistance)
    if attack.name.lower() != "cosmic beam":
        if weakness == attack_type and weakness is not None:
            damage *= 2
        elif resistance == attack_type and resistance is not None:
            damage = max(0, damage - 30)
    return damage


def _attack_options(obs, card_data, attack_data):
    state = obs.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    if not player.active or player.active[0] is None or not opponent.active or opponent.active[0] is None:
        return []
    active = player.active[0]
    defender = opponent.active[0]
    return [
        (attack_options, _effective_damage(active, attack, defender, card_data))
        for attack_options in obs.select.option
        if attack_options.type == OptionType.ATTACK
        for attack in [attack_data.get(attack_options.attackId)]
        if attack is not None
    ]


def _score(option, obs, card_data, attack_data):
    state = obs.current
    player = state.players[state.yourIndex]
    opponent = state.players[1 - state.yourIndex]
    context = _context(obs)
    hand = player.hand or []
    hand_ids = [card.id for card in hand if card is not None]
    field_ids = [card.id for card in _board(player)]
    if option.type == OptionType.END:
        return -100
    if option.type == OptionType.NUMBER:
        return getattr(option, "number", 0)
    if option.type == OptionType.YES:
        return 10
    if option.type == OptionType.NO:
        return 0
    if option.type == OptionType.CARD:
        card = _selected_card(obs, option)
        card_id = getattr(card, "id", None)
        if context == SelectContext.SETUP_ACTIVE_POKEMON:
            return {SOLROCK: 160, RIOLU: 150, MAKUHITA: 120}.get(card_id, 50)
        if context in (SelectContext.TO_BENCH, SelectContext.SETUP_BENCH_POKEMON):
            return {RIOLU: 160 - 20 * _count(player, RIOLU), SOLROCK: 145 - 25 * _count(player, SOLROCK), LUNATONE: 140 - 20 * _count(player, LUNATONE), MAKUHITA: 120}.get(card_id, 40)
        if context == SelectContext.TO_HAND:
            return {MEGA_LUCARIO: 210 if _count(player, RIOLU) else 150, RIOLU: 200 if _count(player, RIOLU) < 2 else 60, SOLROCK: 130, LUNATONE: 125, FIGHTING_ENERGY: 120}.get(card_id, 20)
        if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
            if card_id == MEGA_LUCARIO and len(getattr(card, "energies", [])) >= 2:
                return 400
            if card_id == HARIYAMA and len(getattr(card, "energies", [])) >= 3:
                return 390
            return 100 + len(getattr(card, "energies", [])) * 10
        if context == SelectContext.DISCARD:
            return 5 if card_id == FIGHTING_ENERGY else 60
        return 20
    if option.type == OptionType.ATTACK:
        attack = attack_data.get(option.attackId)
        if attack is None:
            return 20
        active = player.active[0] if player.active else None
        defender = opponent.active[0] if opponent.active else None
        damage = _effective_damage(active, attack, defender, card_data) if active and defender else attack.damage
        score = 100 + damage
        if defender is not None and damage >= defender.hp:
            score += 1000 + _prizes(defender, card_data) * 100
        if attack.name.lower() == "aura jab":
            score += 80
        if attack.name.lower() == "mega brave":
            score += 100
        return score
    if option.type == OptionType.EVOLVE:
        return 190
    if option.type == OptionType.ABILITY:
        source = _zone(state, option.area, state.yourIndex)
        source = source[option.index] if isinstance(option.index, int) and option.index < len(source) else None
        if getattr(source, "id", None) == LUNATONE and _count(player, SOLROCK):
            return 220
        return 100
    if option.type == OptionType.ATTACH:
        target = _target(state, option)
        energy = _hand_card(state, option.index)
        if target is None or energy is None:
            return 0
        count = len(getattr(target, "energies", []))
        if target.id in (RIOLU, MEGA_LUCARIO):
            return 160 + (70 if count < 2 else 0)
        if target.id in (MAKUHITA, HARIYAMA):
            return 145 + (60 if count < 3 else 0)
        if target.id == SOLROCK:
            return 100 if count == 0 and _count(player, LUNATONE) else 20
        return 10
    if option.type == OptionType.PLAY:
        card = _hand_card(state, option.index)
        card_id = getattr(card, "id", None)
        if card_id == DUSK_BALL:
            return 180 if not any(item in field_ids + hand_ids for item in (RIOLU, MEGA_LUCARIO, SOLROCK)) else 90
        if card_id == FIGHTING_GONG:
            return 170
        if card_id == POKE_PAD:
            return 165 if not _count(player, RIOLU) or not _count(player, SOLROCK) else 90
        if card_id == POWER_PRO:
            return 220 if any(item.type == OptionType.ATTACK for item in obs.select.option) else 80
        if card_id == BOSS:
            return 165 if any(target and target.hp <= 540 for target in (opponent.bench or [])) else 30
        if card_id == SWITCH:
            return 150 if len(player.active or []) and player.active[0] and player.active[0].id not in (MEGA_LUCARIO, HARIYAMA) else 65
        if card_id == CARMINE:
            return 180 if state.turn == 1 and state.firstPlayer == state.yourIndex else 25
        if card_id == LILLIE:
            return 170 if len(player.hand or []) <= 3 or len(player.prize or []) == 6 else 110
        if card_id == GRAVITY_MOUNTAIN:
            return 80
        data = card_data.get(card_id)
        if getattr(getattr(data, "cardType", None), "name", "") == "POKEMON":
            return 125
        return 70
    if option.type == OptionType.RETREAT:
        return 100 if any(card.id in (MEGA_LUCARIO, HARIYAMA) and len(card.energies) >= 2 for card in (player.bench or []) if card) else 10
    return 15


def agent(obs_dict):
    try:
        obs = to_observation_class(obs_dict)
        if obs.select is None:
            return _read_deck()
        card_data, attack_data = _metadata()
        options = obs.select.option
        ranked = sorted(range(len(options)), key=lambda i: _score(options[i], obs, card_data, attack_data), reverse=True)
        return ranked[:obs.select.maxCount]
    except Exception:
        if isinstance(obs_dict, dict) and obs_dict.get("select") is None:
            return _read_deck()
        select = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if not isinstance(select, dict):
            return []
        return list(range(select.get("maxCount", 0)))
