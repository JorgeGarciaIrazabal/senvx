import os
import shutil
import subprocess
from json import JSONDecodeError
from pathlib import Path
from sys import platform
from tempfile import TemporaryDirectory
from typing import List, Optional, Union

import filelock
import pydantic
import requests
import typer
from ensureconda import ensureconda

from senvx.models import CombinedCondaLock, LockFileMetaData, Settings

app = typer.Typer(no_args_is_help=True, add_completion=False)



def current_platform() -> str:
    if platform == "linux" or platform == "linux2":
        return "linux-64"
    elif platform == "darwin":
        return "osx-64"
    elif platform == "win32":
        return "win-64"
    else:
        raise NotImplementedError(f"Platform {platform} not supported")


def install_from_lock(
    lock: Union[str, Path], package_name: Optional[str] = None, entry_points=None
) -> None:
    with TemporaryDirectory(prefix="senvx-") as tmp_dir:
        if isinstance(lock, Path) or Path(lock).exists():
            lock_path = Path(str(lock))
        else:
            lock_path = Path(tmp_dir, "lock_file.lock.json")
            lock_path.write_bytes(requests.get(lock, allow_redirects=True).content)

        metadata = _read_metadata(lock_path, package_name, entry_points)
        installation_path = (
            Settings().INSTALLATION_PATH.resolve() / metadata.package_name
        )
        _handle_entry_points_conflicts(metadata)
        _create_conda_environment(lock_path, metadata, installation_path)

        _create_entry_points_symlinks(installation_path, metadata)


def _create_entry_points_symlinks(installation_path, metadata):
    missing_entry_points = [
        ep
        for ep in metadata.entry_points
        if not (installation_path / "bin" / ep).exists()
    ]
    if len(missing_entry_points) > 0:
        if not typer.confirm(
            f"Missing entry_points: [{', '.join(missing_entry_points)}]. Do you want to continue?",
            default=False,
        ):
            typer.echo("Removing environment")
            shutil.rmtree(installation_path)
            raise typer.Abort()

    for entrypoint in metadata.entry_points:
        if entrypoint in missing_entry_points:
            continue
        installation_path / "bin" / entrypoint
        dst = Path(Settings().BIN_DIR / entrypoint)
        src = installation_path / "bin" / entrypoint
        dst.unlink(missing_ok=True)
        os.symlink(src, dst)
        typer.echo(f"Created entry_point {entrypoint} in your bin directory")


def _create_conda_environment(lock_path, metadata, installation_path):
    conda_exe = ensureconda(no_install=True, micromamba=False, mamba=False)
    with TemporaryDirectory(prefix="senvx-") as tmp_dir:
        conda_lock_path = Path(tmp_dir, "lock_file.lock")
        try:
            combined_lock = CombinedCondaLock.parse_file(lock_path)
            conda_lock_path.write_text(
                "@EXPLICIT\n"
                + "\n".join(combined_lock.platform_tar_links[current_platform()])
            )
        except (pydantic.ValidationError, JSONDecodeError):
            # if we can not parse the file, it might be a standard conda lock file,
            # trying to install it anyway
            typer.echo(
                "Warning: No combined lock file, trying to install it directly with conda"
            )
        subprocess.check_call(
            [
                conda_exe,
                "create",
                "-y",
                "--prefix",
                str(installation_path),
                "--file",
                str(conda_lock_path.resolve()),
            ]
        )
        typer.echo(
            f"Installed {metadata.package_name} in {installation_path.resolve()}"
        )


def _handle_entry_points_conflicts(metadata):
    settings = Settings()
    entry_points_conflicts = []
    for entrypoint in metadata.entry_points:
        if Path(settings.BIN_DIR / entrypoint).exists():
            entry_points_conflicts.append(entrypoint)
    if len(entry_points_conflicts) > 0:
        if not typer.confirm(
            f"Entry points {entry_points_conflicts} "
            f"already exists in {settings.BIN_DIR.resolve()}.\n"
            "Do you want to overwrite them?"
        ):
            raise typer.Abort()


def _read_metadata(lock_path, package_name, entry_points):
    try:
        conda_lock = CombinedCondaLock.parse_file(lock_path)
        metadata = conda_lock.metadata
        metadata.package_name = package_name or metadata.package_name
        metadata.entry_points = entry_points or metadata.entry_points
    except (pydantic.ValidationError, JSONDecodeError):
        if entry_points is None:
            typer.echo(
                "Warning: Failed to parse metadata in lockfile and no entry_points provided."
                " Creating the environment with no entry_points"
            )
        metadata = LockFileMetaData(
            package_name=package_name, entry_points=entry_points or []
        )
    if metadata.package_name is None:
        raise typer.Abort(
            "No package_name or metadata found in lockfile."
            " the package name is required to build an environment"
        )
    return metadata


@app.command(no_args_is_help=True)
def install(
    lock_url: Optional[str] = typer.Option(
        None,
        "-l",
        "--lock-url",
        help="lock file url",
    ),
    package_name: Optional[str] = typer.Argument(...),
    entry_points: Optional[List[str]] = typer.Argument(None),
):
    app_path = Path(Settings().INSTALLATION_PATH)
    app_path.mkdir(parents=True, exist_ok=True)
    with filelock.FileLock(str(app_path / "installing.lock"), timeout=60 * 5):
        if lock_url:
            install_from_lock(lock_url, package_name, entry_points)


if __name__ == "__main__":
    app()
