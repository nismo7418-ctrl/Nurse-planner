"""Tests de l'authentification locale (auth.py + écran de connexion dans app.py)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import auth


class TestPasswordApi:
    def test_aucun_mdp_par_defaut(self, fresh_db):
        assert not auth.password_is_set()
        assert not auth.verify_password("n'importe_quoi")

    def test_set_et_verify(self, fresh_db):
        auth.set_password("secret42")
        assert auth.password_is_set()
        assert auth.verify_password("secret42")
        assert not auth.verify_password("mauvais")
        # Le fichier contient un hachage, jamais le mot de passe en clair
        content = (Path(fresh_db.DATA_DIR) / "password.json").read_text(encoding="utf-8")
        assert "secret42" not in content
        assert "pbkdf2_sha256" in content

    def test_mdp_trop_court_refuse(self, fresh_db):
        with pytest.raises(ValueError):
            auth.set_password("123")

    def test_replacement_du_mdp(self, fresh_db):
        auth.set_password("ancien1")
        auth.set_password("nouveau2")
        assert not auth.verify_password("ancien1")
        assert auth.verify_password("nouveau2")

    def test_verrouillage_apres_5_echecs(self, fresh_db):
        """Anti brute-force : 5 tentatives échouées → verrouillage (même mot de passe correct)."""
        assert fresh_db is not None  # fixture : base temporaire + isolation du mot de passe
        auth._lock_reset()  # état propre (le compteur est partagé dans le processus)
        try:
            auth.set_password("secret42")
            for _ in range(5):
                assert not auth.verify_password("mauvais")
            assert auth.lockout_remaining() > 0
            # même le mot de passe correct est refusé pendant le verrouillage
            assert not auth.verify_password("secret42")
        finally:
            auth._lock_reset()  # ne pas impacter les tests suivants


class TestConnexionApp:
    def test_sans_mdp_l_app_est_accessible(self, fresh_db):
        at = AppTest.from_file("app.py", default_timeout=30)
        at.run()
        assert not at.exception
        # Le titre de la page « Aujourd'hui » est visible (pas d'écran de connexion)
        assert any("Aujourd'hui" in (t.value or "") for t in at.title)

    def test_mdp_defini_sans_connexion_ecran_login(self, fresh_db):
        auth.set_password("secret42")
        at = AppTest.from_file("app.py", default_timeout=30)
        at.run()
        assert not at.exception
        assert any("Connexion" in (t.value or "") for t in at.title)
        # La navigation principale n'est PAS affichée
        assert not at.sidebar.radio

    def test_mdp_incorrect_bloque(self, fresh_db):
        auth.set_password("secret42")
        at = AppTest.from_file("app.py", default_timeout=30)
        at.run()
        for ti in at.text_input:
            if ti.label == "Mot de passe":
                ti.set_value("mauvais_mdp")
        for b in at.button:
            if "Se connecter" in (b.label or ""):
                b.click()
                break
        at.run()
        err = " | ".join(e.value for e in at.error)
        assert "incorrect" in err.lower(), err
        # Toujours sur l'écran de connexion
        assert any("Connexion" in (t.value or "") for t in at.title)

    def test_connexion_correcte_affiche_l_app(self, fresh_db):
        auth.set_password("secret42")
        at = AppTest.from_file("app.py", default_timeout=30)
        at.session_state["authenticated"] = True  # simulation d'un login réussi
        at.run()
        assert not at.exception
        assert any("Aujourd'hui" in (t.value or "") for t in at.title)
        assert at.sidebar.radio, "la navigation principale doit être visible"
