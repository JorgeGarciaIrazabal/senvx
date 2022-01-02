from json import JSONDecodeError
from pathlib import Path
from sys import platform

import pydantic
import typer

from senvx.models import CombinedCondaLock, LockFileMetaData, Settings


def current_platform() -> str:
    if platform == "linux" or platform == "linux2":
        return "linux-64"
    elif platform == "darwin":
        return "osx-64"
    elif platform == "win32":
        return "win-64"
    else:
        raise NotImplementedError(f"Platform {platform} not supported")


def handle_entry_points_conflicts(metadata):
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


def read_metadata(lock_path, package_name, entry_points):
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