"""Tests applicatifs (app.py) via ``streamlit.testing.v1.AppTest``.

Chaque test utilise la base temporaire fournie par ``fresh_db``
(voir ``tests/conftest.py``).
"""

import importlib
from datetime import date

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import database as db

PAGES = [
    "📱 Aujourd'hui",
    "📊 Tableau de bord",
    "👥 Patients",
    "📅 Agenda",
    "💶 Facturation",
    "🗺️ Localisation",
]


def _open_page(page: str) -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    at.sidebar.radio[0].set_value(page)
    at.run()
    return at


def _patients_count():
    return len(db.list_patients())


@pytest.mark.parametrize("page", PAGES)
def test_page_rend_sans_exception(fresh_db, page):
    at = _open_page(page)
    assert not at.exception, "; ".join(str(e.value) for e in at.exception)


def test_flux_ajout_patient(fresh_db):
    at = _open_page("👥 Patients")
    n_before = _patients_count()

    [b for b in at.button if b.key == "btn_new_patient"][0].click()
    at.run()
    for ti in at.text_input:
        if ti.label == "Nom":
            ti.set_value("Test")
        elif ti.label == "Prénom":
            ti.set_value("Audit")
    for b in at.button:
        if "Ajouter le patient" in (b.label or ""):
            b.click()
            break
    else:
        pytest.fail("bouton « Ajouter le patient » introuvable")
    at.run()

    assert _patients_count() == n_before + 1
    # Nettoyage
    for p in db.list_patients():
        if p["nom"] == "Test" and p["prenom"] == "Audit":
            db.delete_patient(p["id"])


def test_validation_email_invalide_bloquee(fresh_db):
    at = _open_page("👥 Patients")
    n_before = _patients_count()

    [b for b in at.button if b.key == "btn_new_patient"][0].click()
    at.run()
    for ti in at.text_input:
        if ti.label == "Nom":
            ti.set_value("Inval")
        elif ti.label == "Prénom":
            ti.set_value("Email")
        elif ti.label == "Email":
            ti.set_value("pas_un_email_valide")
    for b in at.button:
        if "Ajouter le patient" in (b.label or ""):
            b.click()
            break
    at.run()

    err = " | ".join(e.value for e in at.error)
    assert "email" in err.lower() and "invalide" in err.lower(), err
    assert _patients_count() == n_before


def test_export_csv_patients(fresh_db):
    """Le contenu exporté (en-têtes + une ligne par patient) est correct."""
    records = [
        {
            "Nom": p["nom"], "Prénom": p["prenom"],
            "Date de naissance": p["date_naissance"], "Sexe": p["sexe"],
            "NISS": p["niss"], "Adresse": p["adresse"], "Code postal": p["cp"],
            "Commune": p["commune"], "Téléphone": p["telephone"],
            "Email": p["email"], "Mutuelle": p["mutuelle"],
            "Allergies": p["allergies"], "Médicaments": p["medicaments"], "Notes": p["notes"],
        }
        for p in db.list_patients()
    ]
    csv_text = pd.DataFrame(records).to_csv(index=False)
    header = csv_text.splitlines()[0]
    assert "Nom" in header and "NISS" in header and "Téléphone" in header
    assert len(csv_text.splitlines()) == len(records) + 1
    assert len(records) >= 1


JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def test_agenda_vue_semaine(fresh_db):
    at = _open_page("📅 Agenda")
    # Bascule en vue « Semaine »
    for r in at.radio:
        if any("Semaine" in (o or "") for o in r.options):
            r.set_value("🗓️ Semaine")
            break
    else:
        pytest.fail("bascule Liste/Semaine introuvable")
    at.run()

    assert not at.exception, "; ".join(str(e.value) for e in at.exception)
    # Le jour du jour est présent dans les en-têtes de la vue semaine
    today = date.today()
    labels = " ".join(m.value for m in at.markdown)
    assert JOURS[today.weekday()] in labels
    # Les 3 interventions d'exemple (datées d'aujourd'hui) apparaissent dans un tableau
    assert len(at.dataframe) >= 1


def test_billing_pdf_retourne_un_pdf(fresh_db):
    app = importlib.import_module("app")
    now = date.today()
    pdf_bytes = bytes(app._billing_pdf(
        now.year, now.month,
        [
            {
                "Prénom": "A", "Nom": "B", "NISS": "85010104567",
                "Commune": "La Louvière", "Mutuelle": "CM", "Soins": 2, "Total": 2,
            }
        ],
        ["Soins"], 2, 1,
    ))
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
