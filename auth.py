"""
Authentification locale (sans serveur, sans base externe).

Le mot de passe est stocké dans un fichier JSON au format ``{"v": 1, "salt": ..., "hash": ...}``
à côté de la base de données (dossier ``data/``, non versionné).

Sécurité :
- Hachage PBKDF2-HMAC-SHA256, **600 000 itérations** (recommandation OWASP 2023),
  module standard uniquement. Les anciens enregistrements (100 000 itérations)
  restent valides : le nombre d'itérations est conservé par hachage.
- **Verrouillage anti brute-force** : après ``MAX_FAILED_ATTEMPTS`` tentatives
  échouées, ``verify_password`` refuse toute tentative pendant
  ``LOCKOUT_SECONDS`` (compteur en mémoire, réinitialisé par succès ou
  redéfinition du mot de passe).
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import time

logger = logging.getLogger("nurse_planner.auth")

PBKDF2_ITERATIONS = 600_000
_ALGO = "pbkdf2_sha256"

# Verrouillage anti brute-force (en mémoire, par processus)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 30.0
_lock = {"failures": 0, "locked_until": 0.0}


def _lock_reset() -> None:
    """Réinitialise le compteur de tentatives échouées."""
    _lock["failures"] = 0
    _lock["locked_until"] = 0.0


def _lock_is_active() -> bool:
    return time.monotonic() < _lock["locked_until"]


def lockout_remaining() -> int:
    """Secondes restantes avant la fin du verrouillage (0 si non verrouillé)."""
    if not _lock_is_active():
        return 0
    return int(_lock["locked_until"] - time.monotonic()) + 1


def _record_failure() -> None:
    _lock["failures"] += 1
    if _lock["failures"] >= MAX_FAILED_ATTEMPTS and not _lock_is_active():
        _lock["locked_until"] = time.monotonic() + LOCKOUT_SECONDS
        logger.warning(
            "Verrouillage de la connexion pendant %.0f s (%d échecs).",
            LOCKOUT_SECONDS, _lock["failures"],
        )


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
    _lock_reset()  # redéfinition du mot de passe : réautoriser les tentatives
    logger.info("Mot de passe de l'application défini (fichier : %s)", path)


def verify_password(password: str) -> bool:
    """Vérifie le mot de passe saisi. Faux si aucun mot de passe n'est défini
    ou si le compte est en verrouissement anti brute-force.

    Le mot de passe saisi n'est JAMAIS journalisé.
    """
    if _lock_is_active():
        logger.warning("Tentative de connexion refusée (verrouissement en cours).")
        return False
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
    if ok:
        _lock_reset()
    else:
        _record_failure()
        logger.warning("Tentative de connexion refusée (mot de passe incorrect).")
    return ok
