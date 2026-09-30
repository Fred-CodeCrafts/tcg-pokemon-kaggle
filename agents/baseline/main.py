import random
import traceback


OPTION_SCORE = {
    8: 600,
    10: 550,
    7: 500,
    9: 450,
    13: 300,
    12: 200,
    14: -100,
    1: 50,
    2: 0,
}

DECK = (1158,) + (721,) * 2 + (722,) * 4 + (723,) * 4 + (1145,) * 4 + (1205,) * 2 + (1227,) * 4 + (1235,) * 4 + (3,) * 35
assert len(DECK) == 60


def read_deck_csv():
    return list(DECK)


def _fallback(select):
    options = select.get("option") or []
    minimum = select.get("minCount", 0)
    maximum = select.get("maxCount", 0)
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        return []
    if minimum < 0 or maximum < minimum or maximum > len(options):
        return []
    return list(range(maximum))


def agent(obs_dict):
    try:
        if not isinstance(obs_dict, dict):
            return []
        select = obs_dict.get("select")
        if select is None:
            return read_deck_csv()
        if not isinstance(select, dict):
            return []

        options = select.get("option") or []
        minimum = select.get("minCount", 0)
        maximum = select.get("maxCount", 0)
        if (
            not isinstance(options, list)
            or not isinstance(minimum, int)
            or not isinstance(maximum, int)
            or minimum < 0
            or maximum < minimum
            or maximum > len(options)
        ):
            return []

        ranked = list(range(len(options)))
        random.shuffle(ranked)
        ranked.sort(
            key=lambda index: -OPTION_SCORE.get(options[index].get("type", -1), 0)
            if isinstance(options[index], dict)
            else 0
        )
        return ranked[:maximum] if maximum else []
    except Exception:
        traceback.print_exc()
        if isinstance(obs_dict, dict) and obs_dict.get("select") is None:
            return list(DECK)
        if isinstance(obs_dict, dict) and isinstance(obs_dict.get("select"), dict):
            return _fallback(obs_dict["select"])
        return []