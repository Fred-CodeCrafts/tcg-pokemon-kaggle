import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CG = (
    ROOT
    / "the-pokemon-company-ptcg-ai-battle-challenge-playground"
    / "sample_submission"
    / "sample_submission"
    / "sample_submission"
)


def _load_mawile(monkeypatch):
    monkeypatch.syspath_prepend(str(SAMPLE_CG))
    main_path = ROOT / "agents" / "mega_mawile_counter" / "main.py"
    spec = importlib.util.spec_from_file_location("mawile_attack_test", main_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _attack_score(module, name, damage, target_hp, target_max_hp, prizes_left):
    attack_id = 1006 if name == "Gobble Down" else 1007
    player = SimpleNamespace(active=[SimpleNamespace(id=695)], prize=[None] * prizes_left)
    opponent = SimpleNamespace(
        active=[SimpleNamespace(id=9999, hp=target_hp, maxHp=target_max_hp)]
    )
    observation = SimpleNamespace(
        current=SimpleNamespace(yourIndex=0, players=[player, opponent], turn=1),
        select=None,
    )
    option = SimpleNamespace(type=module.OptionType.ATTACK, attackId=attack_id)
    attack_data = {attack_id: SimpleNamespace(name=name, damage=damage)}
    return module._option_score(option, observation, {}, attack_data)


def test_zero_prize_gobble_down_ranks_below_ending_turn(monkeypatch):
    module = _load_mawile(monkeypatch)
    player = SimpleNamespace(prize=[None] * 6)
    observation = SimpleNamespace(
        current=SimpleNamespace(yourIndex=0, players=[player, SimpleNamespace(active=[])]),
        select=None,
    )

    gobble_score = _attack_score(module, "Gobble Down", 0, 200, 300, 6)
    end_score = module._option_score(
        SimpleNamespace(type=module.OptionType.END), observation, {}, {}
    )

    assert gobble_score < end_score


def test_gobble_down_uses_prizes_against_damaged_target(monkeypatch):
    module = _load_mawile(monkeypatch)
    gobble_score = _attack_score(module, "Gobble Down", 0, 150, 300, 4)
    huge_bite_score = _attack_score(module, "Huge Bite", 260, 150, 300, 4)

    assert gobble_score > huge_bite_score


def test_huge_bite_remains_preferred_against_undamaged_target(monkeypatch):
    module = _load_mawile(monkeypatch)
    gobble_score = _attack_score(module, "Gobble Down", 0, 300, 300, 6)
    huge_bite_score = _attack_score(module, "Huge Bite", 260, 300, 300, 6)

    assert huge_bite_score > gobble_score