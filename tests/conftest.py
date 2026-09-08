import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from constraint_engine import load_layout, load_parts  # noqa: E402

PARTS_PATH = REPO / "parts" / "ecg-patch-parts.json"
NAIVE_PATH = REPO / "layouts" / "ecg-patch-naive.json"
TARGET_PATH = REPO / "layouts" / "ecg-patch-missionpcb.json"


@pytest.fixture(scope="session")
def repo() -> Path:
    return REPO


@pytest.fixture(scope="session")
def parts():
    loaded, _ = load_parts(PARTS_PATH)
    return loaded


@pytest.fixture(scope="session")
def naive_layout():
    layout, _ = load_layout(NAIVE_PATH)
    return layout


@pytest.fixture(scope="session")
def target_layout():
    layout, _ = load_layout(TARGET_PATH)
    return layout
