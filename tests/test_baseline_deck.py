from agents.baseline import main as baseline


def test_initial_deck_selection_survives_missing_deck_file(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline, "__file__", str(tmp_path / "main.py"))
    monkeypatch.chdir(tmp_path)

    deck = baseline.agent({"current": None, "logs": [], "select": None})

    assert deck == list(baseline.DECK)
    assert len(deck) == 60