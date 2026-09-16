"""Fixtures communes : base de données temporaire et déterministe.

La vraie base ``data/infirmiere.db`` n'est JAMAIS touchée par les tests :
chaque test obtient une base fraîche (données d'exemple issues de
``database.init_db()``) dans un dossier temporaire.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import database as db  # noqa: E402


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Pointe ``database.DB_PATH`` / ``database.DATA_DIR`` sur ``tmp_path``,
    initialise une base fraîche ; ``monkeypatch`` restaure DB_PATH / DATA_DIR
    automatiquement en teardown.
    """
    db_path = tmp_path / "infirmiere.db"
    # monkeypatch restaure DB_PATH / DATA_DIR automatiquement en teardown
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    monkeypatch.setattr(db, "DATA_DIR", str(tmp_path))
    db.init_db()
    yield db
    # monkeypatch restaure automatiquement DB_PATH / DATA_DIR ; les fichiers
    # temporaires (DB, sauvegardes) restent dans tmp_path, nettoyé par pytest.
