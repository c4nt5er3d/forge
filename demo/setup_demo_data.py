from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent
MESSY = ROOT / "messy"
ORGANIZED = ROOT / "organized"


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def main() -> None:
    reset_dir(MESSY)
    reset_dir(ORGANIZED)

    write_file(
        MESSY / "invoice_q1.txt",
        "Quarterly invoice statement for office supplies and software subscriptions.",
    )
    write_file(
        MESSY / "trip_notes.md",
        "# Travel plan\nPacking list and hotel confirmation details for May workshop.",
    )
    write_file(
        MESSY / "script.py",
        "print('demo utility script')\n",
    )
    write_file(
        MESSY / "budget.csv",
        "category,amount\nsoftware,120\ntravel,450\nsupplies,80\n",
    )
    write_file(
        MESSY / "README.tmp.log",
        "temporary app log output for demo sorting\n",
    )

    print("Demo dataset prepared.")
    print(f"Messy folder: {MESSY}")
    print(f"Organized folder: {ORGANIZED}")


if __name__ == "__main__":
    main()
