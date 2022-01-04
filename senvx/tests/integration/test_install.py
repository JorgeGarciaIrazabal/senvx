from senvx.install import install_from_lock
from senvx.tests.conftest import BLACK_METADATA_LOCK


def test_install_black_from_lock(monkeypatch, tmp_path):
    monkeypatch.setenv("SENVX_INSTALLATION_PATH", str(tmp_path / "installation_path"))
    bin_dir = tmp_path / "bin_dir"
    monkeypatch.setenv("SENVX_BIN_DIR", str(bin_dir))
    install_from_lock(lock=BLACK_METADATA_LOCK)

    assert (bin_dir / "black").exists()

