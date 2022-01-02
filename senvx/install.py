import os
import shutil
import subprocess
from json import JSONDecodeError
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Union

import pydantic
import requests
import typer
from ensureconda import ensureconda

from senvx.common import current_platform, handle_entry_points_conflicts, read_metadata
from senvx.models import CombinedCondaLock, Settings


def install_from_lock(
    lock: Union[str, Path], package_name: Optional[str] = None, entry_points=None
) -> None:
    with TemporaryDirectory(prefix="senvx-") as tmp_dir:
        if isinstance(lock, Path) or Path(lock).exists():
            lock_path = Path(str(lock))
        else:
            lock_path = Path(tmp_dir, "lock_file.lock.json")
            lock_path.write_bytes(requests.get(lock, allow_redirects=True).content)

        metadata = read_metadata(lock_path, package_name, entry_points)
        installation_path = (
            Settings().INSTALLATION_PATH.resolve() / metadata.package_name
        )
        handle_entry_points_conflicts(metadata)
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