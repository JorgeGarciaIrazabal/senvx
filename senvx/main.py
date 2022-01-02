from pathlib import Path
from typing import List, Optional

import filelock
import typer

from senvx.install import install_from_lock
from senvx.models import Settings

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command(no_args_is_help=True)
def install(
    lock_uri: Optional[str] = typer.Option(
        None,
        "-l",
        "--lock-uri",
        help="lock file url",
    ),
    package_name: Optional[str] = typer.Argument(...),
    entry_points: Optional[List[str]] = typer.Argument(None),
):
    app_path = Path(Settings().INSTALLATION_PATH)
    app_path.mkdir(parents=True, exist_ok=True)
    with filelock.FileLock(str(app_path / "installing.lock"), timeout=60 * 5):
        if lock_uri:
            install_from_lock(lock_uri, package_name, entry_points)


if __name__ == "__main__":
    app()
