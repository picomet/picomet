import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "startproject", help="Generate project in the current folder using copier."
    )
    parser.add_argument(
        "folder",
        help="The location of the project to be created. Default is the current folder.",
    )

    args = parser.parse_args()

    if args.startproject:
        import copier

        src_path = Path(__file__).parent / "template"

        dst_path = Path(os.getcwd())
        if args.folder:
            dst_path = (dst_path / args.folder).resolve()
            if not dst_path.is_dir():
                dst_path.mkdir(parents=True, exist_ok=True)

        project_name = dst_path.name

        copier.run_copy(
            src_path.as_posix(),
            dst_path.as_posix(),
            data={"PROJECT_NAME": project_name},
            unsafe=True,
        )
