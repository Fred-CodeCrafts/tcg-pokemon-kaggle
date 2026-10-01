import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CG = (
    ROOT
    / "the-pokemon-company-ptcg-ai-battle-challenge-playground"
    / "sample_submission"
    / "sample_submission"
    / "sample_submission"
)


def test_initial_deck_selection_without_module_file(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(SAMPLE_CG))
    monkeypatch.chdir(tmp_path)
    main_path = ROOT / "agents" / "mega_excadrill_counter" / "main.py"
    spec = importlib.util.spec_from_file_location("excadrill_source_loaded", main_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    del module.__file__

    deck = module.agent({"current": None, "logs": [], "select": None})

    assert deck == list(module.FALLBACK_DECK)
    assert len(deck) == 60