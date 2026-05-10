import argparse
import json
import shutil
from pathlib import Path


def load_categories(config_path):
    with open(config_path, "r") as f:
        return json.load(f)


def get_category(extension, categories):
    for category, extensions in categories.items():
        if extension.lower() in extensions:
            return category
    return "Misc"


def resolve_collision(destination):
    if not destination.exists():
        return destination
    counter = 1
    while True:
        new_dest = destination.with_stem(f"{destination.stem}_{counter}")
        if not new_dest.exists():
            return new_dest
        counter += 1


def organize(target, destination, dry_run, categories):
    target = Path(target)
    destination = Path(destination)

    moved = []
    skipped = []

    for file in target.iterdir():
        # skip hidden files, directories, and the script itself
        if file.is_dir() or file.name.startswith("."):
            skipped.append(file.name)
            continue

        category = get_category(file.suffix, categories)
        category_folder = destination / category

        dest_file = resolve_collision(category_folder / file.name)

        if dry_run:
            print(f"[DRY RUN] {file.name} → {category_folder.name}/")
        else:
            category_folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file), str(dest_file))
            print(f"Moved: {file.name} → {category_folder.name}/")
            moved.append(file.name)

    print("\n--- Summary ---")
    if dry_run:
        print("Dry run complete. No files were moved.")
    else:
        print(f"Files moved:   {len(moved)}")
        print(f"Files skipped: {len(skipped)}")


def main():
    parser = argparse.ArgumentParser(
        description="File Organizer — sort any folder automatically."
    )
    parser.add_argument(
        "--target",
        type=str,
        default=".",
        help="Folder to organize (default: current folder)"
    )
    parser.add_argument(
        "--destination",
        type=str,
        default=None,
        help="Where to put sorted folders (default: same as target)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would happen without moving anything"
    )

    args = parser.parse_args()

    target = Path(args.target).resolve()
    destination = Path(args.destination).resolve() if args.destination else target

    # load categories from config
    config_path = Path(__file__).parent.parent / "config" / "categories.json"
    categories = load_categories(config_path)

    print(f"Target:      {target}")
    print(f"Destination: {destination}")
    print(f"Dry run:     {args.dry_run}")
    print()

    organize(target, destination, args.dry_run, categories)


if __name__ == "__main__":
    main()