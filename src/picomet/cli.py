import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "startproject", help="Generate project in the current folder using copier."
    )

    args = parser.parse_args()
    if args.startproject:
        import copier
        from django.core.management.utils import get_random_secret_key

        copier.run_copy((Path(__file__).parent / "template").as_posix())
        with open(".env") as file:
            file_content = file.read()

        modified_content = file_content.replace(
            "SECRET_KEY=", f"SECRET_KEY={get_random_secret_key()}"
        )

        with open(".env", "w") as file:
            file.write(modified_content)
