# Deck Pool

Add one legal deck per `.csv`, with one engine `Card ID` per row and 60 rows total. Validate a list with:

```text
python tools/deck_check.py decks/<name>.csv
```

The round-robin tool uses `agents/baseline/main.py` for every deck and writes a paired-seat win-rate matrix under `runs/`. The supplied sample deck is the only current list, so it cannot produce a matchup ranking by itself.