"""Tests de la couche de persistance (database.py).

Portés depuis la suite d'audit initiale (23 checks) + tests de la rétention
de sauvegardes (prune_backups).
"""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

import database as db_mod


def db_path_join(db, name: str) -> Path:
    return Path(db.DATA_DIR) / name


def _today():
    return date.today().isoformat()


class TestSeedDemoEtConsentement:
    def test_init_db_base_vide_par_defaut(self, tmp_path, monkeypatch):
        """RGPD : par défaut la base fraîche est VIDE (les données de démo sont opt-in)."""
        monkeypatch.setattr(db_mod, "DB_PATH", str(tmp_path / "vide.db"))
        monkeypatch.setattr(db_mod, "DATA_DIR", str(tmp_path))
        db_mod.init_db()
        assert db_mod.list_patients() == []
        assert db_mod.list_interventions() == []
        # seed_demo_data est explicite…
        db_mod.seed_demo_data()
        assert len(db_mod.list_patients()) == 3
        assert len(db_mod.list_interventions()) == 3
        # …et idempotente (un 2e appel ne duplique rien)
        db_mod.seed_demo_data()
        assert len(db_mod.list_patients()) == 3
        assert len(db_mod.list_interventions()) == 3

    def test_consent_date_valeur_par_defaut_et_roundtrip(self, fresh_db):
        """RGPD art. 13-14 : consent_date par défaut vide, modifiable."""
        db = fresh_db
        pid = db.add_patient({
            "nom": "Consent", "prenom": "Test", "date_naissance": "1960-01-01",
            "sexe": "F", "niss": "", "adresse": "", "cp": "", "commune": "",
            "telephone": "", "email": "", "mutuelle": "", "allergies": "",
            "medicaments": "", "notes": "", "lat": None, "lng": None,
        })
        try:
            assert db.get_patient(pid)["consent_date"] == ""
            db.update_patient(pid, {"consent_date": "2026-01-15"})
            assert db.get_patient(pid)["consent_date"] == "2026-01-15"
        finally:
            db.delete_patient(pid)


class TestUpdatePatient:
    def test_update_partiel_lat_lng(self, fresh_db):
        """Cas critique du géocodage : seule lat/lng sont passés."""
        db = fresh_db
        p = db.get_patient(1)
        nom_avant, tel_avant = p["nom"], p["telephone"]

        db.update_patient(1, {"lat": 50.4766, "lng": 4.3340})

        p2 = db.get_patient(1)
        assert p2["nom"] == nom_avant
        assert p2["telephone"] == tel_avant
        assert abs(p2["lat"] - 50.4766) < 1e-9
        assert abs(p2["lng"] - 4.3340) < 1e-9

    def test_update_avec_cles_ignores(self, fresh_db):
        """Les clés inconnues sont ignorées, pas d'erreur SQL."""
        db = fresh_db
        db.update_patient(1, {"champs_inconnu": "x", "nom": "Modifié"})
        assert db.get_patient(1)["nom"] == "Modifié"

    def test_update_vide_nope(self, fresh_db):
        db = fresh_db
        avant = db.get_patient(1)
        db.update_patient(1, {})  # pas de champ autorisé : aucun UPDATE
        assert db.get_patient(1) == avant


class TestUpdateIntervention:
    def test_update_partiel_statut(self, fresh_db):
        db = fresh_db
        i = db.list_interventions()[0]
        type_avant = i["type"]

        db.update_intervention(i["id"], {"statut": "Effectué"})

        i2 = [x for x in db.list_interventions() if x["id"] == i["id"]][0]
        assert i2["statut"] == "Effectué"
        assert i2["type"] == type_avant


class TestBackupRestore:
    def test_backup_creer_fichier_valide(self, fresh_db):
        db = fresh_db
        dest = db.backup()
        assert dest.endswith(".db")
        conn = sqlite3.connect(dest)
        try:
            n = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        finally:
            conn.close()
        assert n == 3

    def test_restore_retablit_la_base(self, fresh_db):
        db = fresh_db
        tel_avant = db.get_patient(1)["telephone"]
        dest = db.backup()

        db.update_patient(1, {"telephone": "0000 00 00 00"})
        assert db.get_patient(1)["telephone"] == "0000 00 00 00"

        db.restore(dest)
        assert db.get_patient(1)["telephone"] == tel_avant

    def test_restore_fichier_manquant(self, fresh_db):
        with pytest.raises(FileNotFoundError):
            fresh_db.restore("/chemin/inexistant/infirmiere.db")


class TestPruneBackups:
    def test_garde_les_k_plus_recentes(self, fresh_db):
        db = fresh_db
        # 7 sauvegardes « historiques » + la DB principale (ne doit pas être touchée)
        for i in range(7):
            fname = f"infirmiere_backup_2026010{i + 1}_120000.db"
            path = db_path_join(db, fname)
            path.write_bytes(b"x" * i)
        autre = db_path_join(db, "autre_fichier.db")
        autre.write_bytes(b"keep")

        removed = db.prune_backups(keep=5)

        remaining = {
            p.name for p in Path(db.DATA_DIR).iterdir()
            if p.name.startswith("infirmiere_backup_")
        }
        assert remaining == {f"infirmiere_backup_2026010{i + 1}_120000.db" for i in range(2, 7)}
        assert len(removed) == 2
        assert (db_path_join(db, "autre_fichier.db")).exists()
        assert (db_path_join(db, "infirmiere.db")).exists()

    def test_sous_le_seuil_rien_supprime(self, fresh_db):
        db = fresh_db
        db_path_join(db, "infirmiere_backup_20260101_120000.db").write_bytes(b"x")
        assert db.prune_backups(keep=5) == []


class TestBillingSummary:
    def test_include_planned(self, fresh_db):
        db = fresh_db
        now = date.today()
        pid = db.add_patient({
            "nom": "Factur", "prenom": "Test", "date_naissance": "1960-01-01",
            "sexe": "F", "niss": "85010104567", "adresse": "rue Test", "cp": "7100",
            "commune": "La Louvière", "telephone": "0471000000", "email": "",
            "mutuelle": "CM", "allergies": "", "medicaments": "", "notes": "",
            "lat": None, "lng": None,
        })
        i_done = db.add_intervention({
            "patient_id": pid, "type": "Soins", "date": _today(), "heure": "09:00",
            "duree_min": 30, "statut": "Effectué", "lieu": "", "notes": ""})
        i_planned = db.add_intervention({
            "patient_id": pid, "type": "Soins", "date": _today(), "heure": "10:00",
            "duree_min": 30, "statut": "Planifié", "lieu": "", "notes": ""})
        try:
            only_done = db.billing_summary(now.year, now.month, include_planned=False)
            t_done = sum(r["total"] for r in only_done if r["id"] == pid)
            assert t_done == 1

            with_planned = db.billing_summary(now.year, now.month, include_planned=True)
            t_planned = sum(r["total"] for r in with_planned if r["id"] == pid)
            assert t_planned == 2

            # Une intervention annulée ne compte jamais
            db.update_intervention(i_planned, {"statut": "Annulé"})
            t_after_cancel = sum(
                r["total"] for r in db.billing_summary(now.year, now.month, include_planned=True)
                if r["id"] == pid)
            assert t_after_cancel == 1
        finally:
            db.delete_intervention(i_done)
            db.delete_intervention(i_planned)
            db.delete_patient(pid)
