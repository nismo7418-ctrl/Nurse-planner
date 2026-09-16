"""
Authentification locale (sans serveur, sans base externe).

Le mot de passe est stocké dans un fichier JSON au format ``{"v": 1, "salt": ..., "hash": ...}``
à côté de la base de données (dossier ``data/``, non versionné).
Hachage : PBKDF2-HMAC-SHA256 (100 000 itérations), module standard uniquement.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets

logger = logging.getLogger("nurse_planner.auth")

PBKDF2_ITERATIONS = 100_000
_ALGO = "pbkdf2_sha256"


def _pwd_path() -> str:
    import database as db

    return os.path.join(db.DATA_DIR, "password.json")


def password_is_set() -> bool:
    """Vrai si un mot de passe a déjà été défini."""
    path = _pwd_path()
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        return record.get("algo") == _ALGO and "hash" in record and "salt" in record
    except (json.JSONDecodeError, OSError):
        return False


def set_password(password: str) -> None:
    """Définit (ou remplace) le mot de passe de l'application."""
    if not password or len(password) < 4:
        raise ValueError("Le mot de passe doit contenir au moins 4 caractères.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    record = {
        "v": 1,
        "algo": _ALGO,
        "iterations": PBKDF2_ITERATIONS,
        "salt": salt.hex(),
        "hash": digest.hex(),
    }
    path = _pwd_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # système sans support chmod (rare sur Windows)
    logger.info("Mot de passe de l'application défini (fichier : %s)", path)


def verify_password(password: str) -> bool:
    """Vérifie le mot de passe saisi. Faux si aucun mot de passe n'est défini."""
    if not password_is_set():
        return False
    path = _pwd_path()
    with open(path, "r", encoding="utf-8") as f:
        record = json.load(f)
    salt = bytes.fromhex(record["salt"])
    iterations = int(record.get("iterations", PBKDF2_ITERATIONS))
    expected = bytes.fromhex(record["hash"])
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    ok = hmac.compare_digest(digest, expected)
    if not ok:
        logger.warning("Tentative de connexion refusée (mot de passe incorrect).")
    return ok
