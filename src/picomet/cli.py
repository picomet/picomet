import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "startproject", help="Generate project in the current folder using copier."
    )

    args = parser.parse_args()
    if args.startproject:
        import copier

        copier.run_copy((Path(__file__).parent / "template").as_posix(), unsafe=True)
