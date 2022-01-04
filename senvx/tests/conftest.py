from pathlib import Path

TESTS_PATH = Path(__file__).parent.resolve()
STATIC_PATH = TESTS_PATH / "static"

BLACK_METADATA_LOCK = STATIC_PATH / "black-with-meta.lock.json"
BLACK_NO_NAME_LOCK = STATIC_PATH / "black-with-no-name.lock.json"
BLACK_CORRUPTED_LOCK = STATIC_PATH / "black-corrupted.lock.json"
BLACK_STANDARD_LOCK = STATIC_PATH / "black-corrupted.lock.json"