"""
Couche de persistance (SQLite) pour l'application de l'infirmière à domicile.

Gère les patients et les interventions (soins, toilette, pansement, prise de sang),
ainsi que la facturation mensuelle et les sauvegardes.
"""

import logging
import sqlite3
import os
import re
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger("nurse_planner.database")
if not logging.getLogger().handlers and not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

# Dossier de données (créé automatiquement).
# Surchargeable via NURSE_DATA_DIR (ex. /data dans le conteneur Docker).
DATA_DIR = os.environ.get(
    "NURSE_DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
)
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "infirmiere.db")

# Types d'intervention disponibles
TYPES_INTERVENTION = {
    "Soins": "Soins généraux / infirmiers",
    "Toilette": "Toilette / hygiène",
    "Pansement": "Pansement / cicatrisation",
    "Prise de sang": "Prise de sang / prélèvement",
    "Injection": "Injection / administration",
    "Surveillance": "Surveillance / contrôle",
}

STATUTS = {
    "Planifié": "Planifié",
    "Effectué": "Effectué",
    "Annulé": "Annulé",
}


@contextmanager
def get_conn():
    """Ouvre une connexion SQLite avec un curseur et gère la transaction."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn):
    """Ajoute les colonnes manquantes sur une base existante (migration légère)."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(patients)")
    cols = {row["name"] for row in cur.fetchall()}
    if "niss" not in cols:
        cur.execute("ALTER TABLE patients ADD COLUMN niss TEXT")
    if "consent_date" not in cols:
        cur.execute("ALTER TABLE patients ADD COLUMN consent_date TEXT")


def init_db():
    """Crée les tables si elles n'existent pas et insère des données d'exemple."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                prenom TEXT NOT NULL,
                date_naissance TEXT,
                sexe TEXT,
                niss TEXT,
                adresse TEXT,
                cp TEXT,
                commune TEXT,
                telephone TEXT,
                email TEXT,
                mutuelle TEXT,
                allergies TEXT,
                medicaments TEXT,
                notes TEXT,
                consent_date TEXT,
                lat REAL,
                lng REAL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS interventions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                heure TEXT,
                duree_min INTEGER DEFAULT 30,
                statut TEXT DEFAULT 'Planifié',
                lieu TEXT,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
            )
            """
        )
        _migrate(conn)
        conn.commit()


def seed_demo_data():
    """Insère des patients/interventions d'exemple — UNIQUEMENT si la base est vide.

    RGPD : par défaut l'application démarre avec une base **vide** ; les données
    de démonstration (personnes fictives avec des données de santé) ne sont
    chargées qu'explicitement via l'environnement ``NURSE_SEED_DEMO=1``.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM patients")
        if cur.fetchone()["n"] > 0:
            return

        # Quelques patients d'exemple dans la zone de La Louvière
        exemples = [
            {
                "nom": "Dupont", "prenom": "Marie", "date_naissance": "1948-03-12",
                "sexe": "F", "niss": "48031201234",
                "adresse": "12 rue des Tilleuls", "cp": "7100",
                "commune": "La Louvière", "telephone": "0471 12 34 56",
                "mutuelle": "Solidaris", "allergies": "Pénicilline",
                "medicaments": "Metformine 500mg", "lat": 50.4766, "lng": 4.3340,
            },
            {
                "nom": "Martin", "prenom": "Jean", "date_naissance": "1955-07-22",
                "sexe": "H", "niss": "55072204567",
                "adresse": "8 avenue de la Station", "cp": "7100",
                "commune": "La Louvière", "telephone": "0472 98 76 54",
                "mutuelle": "CM", "allergies": "", "medicaments": "Amlodipine 5mg",
                "lat": 50.4790, "lng": 4.3310,
            },
            {
                "nom": "Lefevre", "prenom": "Sophie", "date_naissance": "1962-11-05",
                "sexe": "F", "niss": "62110507890",
                "adresse": "3 place de l'Église", "cp": "7130",
                "commune": "Châtelineau", "telephone": "0475 55 44 33",
                "mutuelle": "Solidaris", "allergies": "Latex",
                "medicaments": "Levothyroxine 75µg", "lat": 50.4520, "lng": 4.3600,
            },
        ]
        for p in exemples:
            cur.execute(
                """
                INSERT INTO patients (nom, prenom, date_naissance, sexe, niss, adresse, cp,
                    commune, telephone, email, mutuelle, allergies, medicaments, notes, lat, lng)
                VALUES (:nom, :prenom, :date_naissance, :sexe, :niss, :adresse, :cp,
                    :commune, :telephone, :email, :mutuelle, :allergies, :medicaments,
                    :notes, :lat, :lng)
                """,
                {**p, "email": "", "notes": ""},
            )

        # Quelques interventions d'exemple
        from datetime import date
        today = date.today().isoformat()
        cur.execute(
            """
            INSERT INTO interventions (patient_id, type, date, heure, duree_min, statut, lieu, notes)
            VALUES (1, 'Pansement', ?, '09:00', 45, 'Planifié', 'Domicile', 'Cicatrice jambe gauche')
            """,
            (today,),
        )
        cur.execute(
            """
            INSERT INTO interventions (patient_id, type, date, heure, duree_min, statut, lieu, notes)
            VALUES (2, 'Prise de sang', ?, '10:30', 20, 'Planifié', 'Domicile', 'Bilan glycémie')
            """,
            (today,),
        )
        cur.execute(
            """
            INSERT INTO interventions (patient_id, type, date, heure, duree_min, statut, lieu, notes)
            VALUES (3, 'Toilette', ?, '14:00', 60, 'Planifié', 'Domicile', '')
            """,
            (today,),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

def list_patients():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM patients ORDER BY nom, prenom"
        ).fetchall()
    return [dict(r) for r in rows]


def get_patient(patient_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return dict(row) if row else None


def add_patient(data: dict):
    data = dict(data)
    data.setdefault("consent_date", "")
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO patients (nom, prenom, date_naissance, sexe, niss, adresse, cp, commune,
                telephone, email, mutuelle, allergies, medicaments, notes, consent_date, lat, lng)
            VALUES (:nom, :prenom, :date_naissance, :sexe, :niss, :adresse, :cp, :commune,
                :telephone, :email, :mutuelle, :allergies, :medicaments, :notes,
                :consent_date, :lat, :lng)
            """,
            data,
        )
        return cur.lastrowid


def update_patient(patient_id, data: dict):
    """Met à jour UNIQUEMENT les champs fournis (mise à jour partielle).

    Exemple : update_patient(1, {"lat": 50.47, "lng": 4.33}) ne touche que lat/lng.
    """
    allowed = ["nom", "prenom", "date_naissance", "sexe", "niss", "adresse", "cp", "commune",
               "telephone", "email", "mutuelle", "allergies", "medicaments", "notes",
               "consent_date", "lat", "lng"]
    fields = [k for k in data if k in allowed]
    if not fields:
        return
    data = {k: data[k] for k in fields}
    data["id"] = patient_id
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    with get_conn() as conn:
        conn.execute(f"UPDATE patients SET {set_clause} WHERE id = :id", data)


def delete_patient(patient_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM interventions WHERE patient_id = ?", (patient_id,))
        conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------

def list_interventions(patient_id=None, date=None, statut=None):
    query = """
        SELECT i.*, p.nom, p.prenom, p.adresse, p.cp, p.commune, p.telephone
        FROM interventions i
        JOIN patients p ON p.id = i.patient_id
        WHERE 1=1
    """
    params = []
    if patient_id is not None:
        query += " AND i.patient_id = ?"
        params.append(patient_id)
    if date is not None:
        query += " AND i.date = ?"
        params.append(date)
    if statut is not None:
        query += " AND i.statut = ?"
        params.append(statut)
    query += " ORDER BY i.date, i.heure"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def add_intervention(data: dict):
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO interventions (patient_id, type, date, heure, duree_min, statut, lieu, notes)
            VALUES (:patient_id, :type, :date, :heure, :duree_min, :statut, :lieu, :notes)
            """,
            data,
        )
        return cur.lastrowid


def update_intervention(intervention_id, data: dict):
    """Met à jour UNIQUEMENT les champs fournis (mise à jour partielle)."""
    allowed = ["patient_id", "type", "date", "heure", "duree_min", "statut", "lieu", "notes"]
    fields = [k for k in data if k in allowed]
    if not fields:
        return
    data = {k: data[k] for k in fields}
    data["id"] = intervention_id
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    with get_conn() as conn:
        conn.execute(f"UPDATE interventions SET {set_clause} WHERE id = :id", data)


def set_statut(intervention_id, statut):
    with get_conn() as conn:
        conn.execute("UPDATE interventions SET statut = ? WHERE id = ?", (statut, intervention_id))


def delete_intervention(intervention_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM interventions WHERE id = ?", (intervention_id,))


# ---------------------------------------------------------------------------
# Statistiques & facturation
# ---------------------------------------------------------------------------

def stats():
    """Statistiques pour le tableau de bord (chiffres du jour + répartition globale)."""
    with get_conn() as conn:
        total_patients = conn.execute("SELECT COUNT(*) AS n FROM patients").fetchone()["n"]
        today = datetime.now().strftime("%Y-%m-%d")
        du_jour = conn.execute(
            "SELECT COUNT(*) AS n FROM interventions WHERE date = ?", (today,)
        ).fetchone()["n"]
        effectuees_jour = conn.execute(
            "SELECT COUNT(*) AS n FROM interventions WHERE date = ? AND statut = 'Effectué'",
            (today,),
        ).fetchone()["n"]
        planifiees_jour = conn.execute(
            "SELECT COUNT(*) AS n FROM interventions WHERE date = ? AND statut = 'Planifié'",
            (today,),
        ).fetchone()["n"]
        par_type = conn.execute(
            "SELECT type, COUNT(*) AS n FROM interventions GROUP BY type ORDER BY n DESC"
        ).fetchall()
    return {
        "total_patients": total_patients,
        "du_jour": du_jour,
        "effectuees_jour": effectuees_jour,
        "planifiees_jour": planifiees_jour,
        "par_type": [dict(r) for r in par_type],
    }


def billing_summary(year: int, month: int, include_planned: bool = True):
    """Récapitulatif de facturation par patient pour un mois donné.

    include_planned=True  : compte les interventions non annulées (Planifié + Effectué).
    include_planned=False : ne compte que les interventions « Effectué »
                            (recommandé pour la facturation mutuelle).
    Retourne une liste de dicts : id, nom, prenom, niss, commune, mutuelle,
    types (dict type -> nombre), total.
    """
    month_start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        month_end = f"{year:04d}-12-31"
    else:
        next_first = datetime.fromisoformat(f"{year:04d}-{month + 1:02d}-01")
        month_end = (next_first - timedelta(days=1)).strftime("%Y-%m-%d")

    types = list(TYPES_INTERVENTION.keys())
    statut_clause = "i.statut != 'Annulé'" if include_planned else "i.statut = 'Effectué'"
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT p.id, p.nom, p.prenom, p.niss, p.commune, p.mutuelle,
                   i.type, COUNT(*) AS n
            FROM interventions i
            JOIN patients p ON p.id = i.patient_id
            WHERE i.date >= ? AND i.date <= ? AND {statut_clause}
            GROUP BY p.id, i.type
            ORDER BY p.nom, p.prenom
            """,
            (month_start, month_end),
        ).fetchall()

    from collections import OrderedDict
    patients = OrderedDict()
    for r in rows:
        pid = r["id"]
        if pid not in patients:
            patients[pid] = {
                "id": pid,
                "nom": r["nom"],
                "prenom": r["prenom"],
                "niss": r["niss"] or "",
                "commune": r["commune"] or "",
                "mutuelle": r["mutuelle"] or "",
                "types": {t: 0 for t in types},
            }
        if r["type"] in patients[pid]["types"]:
            patients[pid]["types"][r["type"]] = r["n"]

    result = []
    for p in patients.values():
        p["total"] = sum(p["types"].values())
        result.append(p)
    return result


# ---------------------------------------------------------------------------
# Sauvegarde / restauration
# ---------------------------------------------------------------------------

def backup():
    """Copie la base de données dans un fichier horodaté. Retourne le chemin.

    Utilise l'API de sauvegarde en ligne de SQLite (sqlite3.Connection.backup),
    qui produit une copie cohérente même si la base est ouverte/écrite ailleurs
    (contrairement à une simple copie de fichier, fragile sous Windows).
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(DATA_DIR, f"infirmiere_backup_{stamp}.db")
    src = sqlite3.connect(DB_PATH)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    logger.info("Sauvegarde créée : %s", dest)
    return dest


def prune_backups(keep: int = 5) -> list:
    """Supprime les plus anciennes sauvegardes, en ne gardant que `keep` fichiers récents.

    Retourne la liste des chemins supprimés. Ignore les fichiers qui ne
    correspondent pas au schéma de nommage des sauvegardes.
    """
    pattern = re.compile(r"^infirmiere_backup_\d{8}_\d{6}\.db$")
    try:
        files = [f for f in os.listdir(DATA_DIR) if pattern.match(f)]
    except FileNotFoundError:
        return []
    files.sort()  # le nom est horodaté : le tri croissant = du plus ancien au plus récent
    to_delete = files[:-keep] if keep < len(files) else []
    removed = []
    for f in to_delete:
        path = os.path.join(DATA_DIR, f)
        try:
            os.remove(path)
            removed.append(path)
            logger.info("Ancienne sauvegarde supprimée : %s", path)
        except OSError as exc:
            logger.warning("Impossible de supprimer la sauvegarde %s : %s", path, exc)
    return removed


def restore(src_path: str):
    """Restaure la base de données depuis un fichier de sauvegarde.

    Utilise l'API de sauvegarde en ligne de SQLite pour une copie cohérente.
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(src_path)
    logger.info("Restauration depuis %s", src_path)
    src = sqlite3.connect(src_path)
    try:
        dst = sqlite3.connect(DB_PATH)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
