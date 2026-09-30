import argparse
import shutil
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if __package__:
    from .arena import run_arena
    from .deck_check import DEFAULT_CARD_DATA, load_card_data, read_deck, validate_deck
else:
    from arena import run_arena
    from deck_check import DEFAULT_CARD_DATA, load_card_data, read_deck, validate_deck


def build_submission(agent_dir, output, max_size_mib=197.7):
    agent_dir = Path(agent_dir).resolve()
    main_path = agent_dir / "main.py"
    deck_path = agent_dir / "deck.csv"
    cg_path = agent_dir / "cg"
    if not main_path.is_file() or not deck_path.is_file():
        raise FileNotFoundError("agent directory must contain main.py and deck.csv")

    deck_errors = validate_deck(read_deck(deck_path), load_card_data(DEFAULT_CARD_DATA))
    if deck_errors:
        raise ValueError("invalid deck: " + "; ".join(deck_errors))

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ptcg_package_") as temporary:
        temporary = Path(temporary)
        archive_path = temporary / "submission.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(main_path, arcname="main.py")
            archive.add(deck_path, arcname="deck.csv")
            if cg_path.is_dir():
                archive.add(cg_path, arcname="cg")

        if archive_path.stat().st_size > max_size_mib * 1024 * 1024:
            raise ValueError(f"archive exceeds the {max_size_mib:g} MiB size limit")
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            roots = {member.name.split("/", 1)[0] for member in members}
            expected_roots = {"deck.csv", "main.py"}
            if cg_path.is_dir():
                expected_roots.add("cg")
            if roots != expected_roots:
                names = sorted(member.name for member in members)
                raise ValueError(f"unexpected archive layout: {names}")
            extracted = temporary / "agent"
            archive.extractall(extracted, filter="data")

        smoke_csv = temporary / "smoke.csv"
        smoke_rows = run_arena(
            extracted,
            extracted,
            matches=1,
            workers=1,
            timeout=120.0,
            seed=20260930,
            output=smoke_csv,
        )
        if len(smoke_rows) != 1 or smoke_rows[0]["winner"] not in {"agent_a", "agent_b"}:
            raise RuntimeError("packaged agent did not finish a local best-of-three match")
        if smoke_rows[0]["errors"]:
            raise RuntimeError(f"packaged agent produced errors: {smoke_rows[0]['errors']}")
        shutil.copyfile(archive_path, output)

    return output


def main():
    parser = argparse.ArgumentParser(description="Build and locally smoke-test a Kaggle tar.gz submission")
    parser.add_argument("agent_dir", nargs="?", default=str(ROOT / "agents" / "baseline"))
    parser.add_argument("--output", default=str(ROOT / "submission.tar.gz"))
    parser.add_argument("--max-size-mib", type=float, default=197.7)
    args = parser.parse_args()
    try:
        output = build_submission(args.agent_dir, args.output, args.max_size_mib)
    except (FileNotFoundError, FileExistsError, OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"package failed: {exc}\n")
    print(f"Submission archive: {output} ({output.stat().st_size / (1024 * 1024):.3f} MiB)")
    print("Contents: main.py, deck.csv at archive root; local match passed")


if __name__ == "__main__":
    main()