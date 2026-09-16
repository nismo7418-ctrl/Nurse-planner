"""
🩺 Infirmière à Domicile — Wallonie (La Louvière)
Application Streamlit de gestion des patients, des soins et de la localisation.

Lancement :
    streamlit run app.py
"""

import html
import logging
import os
import re
import tempfile
import urllib.parse

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta

import database as db
import auth

logger = logging.getLogger("nurse_planner.app")

VERSION = "1.4.0"  # garder aligné avec pyproject.toml / README

# ---------------------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Infirmière à Domicile — La Louvière",
    page_icon="icons/icon_32.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Manifeste PWA : permet « Ajouter à l'écran d'accueil » sur téléphone
# (nécessite un accès en HTTPS pour l'installation, voir README).
if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")):
    st.markdown(
        '<link rel="manifest" href="manifest.json">'
        '<meta name="theme-color" content="#2563eb">',
        unsafe_allow_html=True,
    )

# Initialisation de la base de données
db.init_db()


# RGPD : par défaut la base démarre VIDE. Les données de démonstration
# (personnes fictives avec données de santé) ne sont chargées qu'explicitement.
if os.environ.get("NURSE_SEED_DEMO", "").strip().lower() in ("1", "true", "oui", "yes"):
    db.seed_demo_data()

# Couleurs par type d'intervention
TYPE_COLORS = {
    "Soins": "#2563eb",
    "Toilette": "#0891b2",
    "Pansement": "#d97706",
    "Prise de sang": "#dc2626",
    "Injection": "#7c3aed",
    "Surveillance": "#059669",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def age_from_date(date_naissance):
    if not date_naissance:
        return ""
    try:
        d = datetime.strptime(date_naissance, "%Y-%m-%d")
        today = date.today()
        return today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    except Exception:
        return ""


def intervention_badge(typ):
    color = TYPE_COLORS.get(typ, "#6b7280")
    return (
        f"<span style='background:{color};color:white;padding:2px 10px;"
        f"border-radius:12px;font-size:0.8rem;font-weight:600'>{typ}</span>"
    )


# ---------------------------------------------------------------------------
# Page : Tableau de bord
# ---------------------------------------------------------------------------
def page_dashboard():
    st.title("🩺 Tableau de bord")
    st.caption("Vue d'ensemble de votre activité — La Louvière & alentours")

    s = db.stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Patients", s["total_patients"])
    c2.metric("📅 Interventions du jour", s["du_jour"])
    c3.metric("✅ Effectuées aujourd'hui", s["effectuees_jour"])
    c4.metric("🕒 Planifiées aujourd'hui", s["planifiees_jour"])

    st.divider()

    left, right = st.columns([3, 2])

    with left:
        st.subheader("📋 Interventions du jour")
        today = date.today().isoformat()
        interventions = db.list_interventions(date=today)
        if not interventions:
            st.info("Aucune intervention prévue aujourd'hui.")
        else:
            df = pd.DataFrame(interventions)
            df = df[["heure", "prenom", "nom", "type", "statut", "lieu", "notes"]]
            df["Patient"] = df["prenom"] + " " + df["nom"]
            df = df[["heure", "Patient", "type", "statut", "lieu", "notes"]]
            df.columns = ["Heure", "Patient", "Type", "Statut", "Lieu", "Notes"]
            st.dataframe(df, width="stretch", hide_index=True)

            # Actions rapides
            st.markdown("**Actions rapides**")
            for row in interventions:
                if row["statut"] == "Planifié":
                    col1, col2, col3 = st.columns([3, 1, 1])
                    label = f"{row['heure'] or '—'} · {row['prenom']} {row['nom']} · {row['type']}"
                    with col1:
                        st.markdown(label, unsafe_allow_html=True)
                        _adresse = " ".join(filter(None, [row["adresse"], row["cp"], row["commune"]]))
                        _links = _action_links(row["telephone"], _adresse)
                        if _links:
                            st.markdown("   ·   ".join(_links), unsafe_allow_html=True)
                    with col2:
                        if st.button("✅ Effectué", key=f"ok_{row['id']}"):
                            db.set_statut(row["id"], "Effectué")
                            st.rerun()
                    with col3:
                        if st.button("❌ Annulé", key=f"no_{row['id']}"):
                            db.set_statut(row["id"], "Annulé")
                            st.rerun()
    with right:
        st.subheader("📊 Répartition par type")
        if s["par_type"]:
            df = pd.DataFrame(s["par_type"])
            st.bar_chart(df.set_index("type")["n"], width="stretch")
        else:
            st.info("Aucune donnée.")

        st.markdown("**Légende des soins**")
        for typ, desc in db.TYPES_INTERVENTION.items():
            st.markdown(f"{intervention_badge(typ)}  {desc}", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page : Patients
# ---------------------------------------------------------------------------
def _patient_form(existing=None, key_prefix="new"):
    """Formulaire patient. Retourne un dict ou None."""
    with st.form(f"patient_form_{key_prefix}"):
        st.markdown("**Identité**")
        c1, c2 = st.columns(2)
        prenom = c1.text_input("Prénom", value=existing["prenom"] if existing else "")
        nom = c2.text_input("Nom", value=existing["nom"] if existing else "")
        c3, c4 = st.columns(2)
        date_naissance = c3.date_input(
            "Date de naissance",
            value=datetime.strptime(existing["date_naissance"], "%Y-%m-%d").date()
            if existing and existing.get("date_naissance") else None,
            max_value=date.today(),  # le sélecteur n'offre aucune date future
            help="La date de naissance ne peut pas être dans le futur.",
        )
        sexe = c4.selectbox("Sexe", ["", "F", "H"],
                            index=["", "F", "H"].index(existing["sexe"]) if existing and existing.get("sexe") else 0)

        st.markdown("**Coordonnées**")
        c5, c6 = st.columns(2)
        adresse = c5.text_input("Adresse", value=existing["adresse"] if existing else "")
        cp = c6.text_input("Code postal", value=existing["cp"] if existing else "")
        c7, c8 = st.columns(2)
        commune = c7.text_input("Commune", value=existing["commune"] if existing else "",
                                placeholder="La Louvière, Châtelineau, ...")
        telephone = c8.text_input("Téléphone", value=existing["telephone"] if existing else "")

        c9, c10 = st.columns(2)
        email = c9.text_input("Email", value=existing["email"] if existing else "")
        mutuelle = c10.text_input("Mutuelle", value=existing["mutuelle"] if existing else "",
                                  placeholder="Solidaris, CM, ...")
        niss = st.text_input(
            "NISS (n° sécurité sociale)",
            value=existing["niss"] if existing else "",
            placeholder="11 chiffres — requis pour la facturation",
        )

        st.markdown("**Traitements & consentement**")
        consent_date = st.date_input(
            "🔐 Consentement du patient (date d'information)",
            value=datetime.strptime(existing["consent_date"], "%Y-%m-%d").date()
            if existing and existing.get("consent_date") else None,
            max_value=date.today(),
            help="RGPD (art. 13-14) : date à laquelle le patient a été informé du "
            "traitement de ses données et a consenti. Laissez vide si non documenté.",
        )

        st.markdown("**Informations médicales**")
        allergies = st.text_area("Allergies", value=existing["allergies"] if existing else "")
        medicaments = st.text_area("Médicaments en cours",
                                   value=existing["medicaments"] if existing else "")
        notes = st.text_area("Notes", value=existing["notes"] if existing else "")

        submitted = st.form_submit_button(
            "💾 Mettre à jour" if existing else "➕ Ajouter le patient",
            width="stretch",
        )
        if not submitted:
            return None

        # Validation non bloquante : TOUTES les erreurs sont listées d'un coup
        # (au lieu de bloquer sur la première et de forcer à resoumettre).
        errors = []
        if not prenom.strip() or not nom.strip():
            errors.append("Le prénom et le nom sont obligatoires.")
        if date_naissance and date_naissance > date.today():
            errors.append("La date de naissance ne peut pas être dans le futur.")
        email_clean = email.strip()
        if email_clean and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email_clean):
            errors.append(f"Adresse email invalide : {email_clean}")
        tel_clean = telephone.strip()
        if tel_clean:
            tel_digits = re.sub(r"\D", "", tel_clean)
            if not (8 <= len(tel_digits) <= 13):
                errors.append("Numéro de téléphone invalide (8 à 13 chiffres attendus).")
        if errors:
            for err in errors:
                st.error(err)
            return None

        niss_clean = niss.replace(" ", "")
        if niss_clean and not (niss_clean.isdigit() and len(niss_clean) == 11):
            st.warning("⚠️ Le NISS doit contenir 11 chiffres (vérifiez avant de facturer).")

        return {
            "nom": nom.strip(),
            "prenom": prenom.strip(),
            "date_naissance": date_naissance.isoformat() if date_naissance else "",
            "sexe": sexe,
            "niss": niss_clean,
            "adresse": adresse.strip(),
            "cp": cp.strip(),
            "commune": commune.strip(),
            "telephone": telephone.strip(),
            "email": email.strip(),
            "mutuelle": mutuelle.strip(),
            "allergies": allergies.strip(),
            "medicaments": medicaments.strip(),
            "notes": notes.strip(),
            "consent_date": consent_date.isoformat() if consent_date else "",
            "lat": existing.get("lat") if existing else None,
            "lng": existing.get("lng") if existing else None,
        }


def page_patients():
    st.title("👥 Patients")
    st.caption("Gérez votre dossier de patients")

    patients = db.list_patients()

    # Recherche
    search = st.text_input("🔍 Rechercher un patient (nom, commune, téléphone)...")
    if search:
        q = search.lower()
        patients = [
            p for p in patients
            if q in p["nom"].lower() or q in p["prenom"].lower()
            or q in (p["commune"] or "").lower() or q in (p["telephone"] or "").lower()
        ]

    # Bouton « Nouveau patient » toujours disponible
    if st.button("➕ Nouveau patient", key="btn_new_patient", type="primary"):
        st.session_state["patient_new"] = True
        st.session_state.pop("selected_patient", None)
        st.rerun()

    # Export CSV de la liste des patients
    if patients:
        _recs = []
        for p in patients:
            _recs.append({
                "Nom": p["nom"], "Prénom": p["prenom"],
                "Date de naissance": p["date_naissance"], "Sexe": p["sexe"],
                "NISS": p["niss"], "Adresse": p["adresse"], "Code postal": p["cp"],
                "Commune": p["commune"], "Téléphone": p["telephone"],
                "Email": p["email"], "Mutuelle": p["mutuelle"],
                "Allergies": p["allergies"], "Médicaments": p["medicaments"],
                "Notes": p["notes"],
                "Consentement (date)": p.get("consent_date") or "",
            })
        _csv = pd.DataFrame(_recs).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Exporter la liste (CSV)", data=_csv,
            file_name=f"patients_{date.today().isoformat()}.csv", mime="text/csv",
        )

    left, right = st.columns([2, 3])

    with left:
        st.markdown("**Liste des patients**")
        if not patients:
            st.info("Aucun patient trouvé.")
        for p in patients:
            age = age_from_date(p["date_naissance"])
            label = f"{p['prenom']} {p['nom']}" + (f" ({age} ans)" if age else "")
            if st.button(label, key=f"sel_{p['id']}", width="stretch"):
                st.session_state["selected_patient"] = p["id"]
                st.session_state.pop("patient_new", None)
                st.rerun()

    with right:
        if st.session_state.get("patient_new"):
            st.markdown("**➕ Nouveau patient**")
            data = _patient_form(key_prefix="new")
            if data:
                new_id = db.add_patient(data)
                st.session_state["selected_patient"] = new_id
                st.session_state.pop("patient_new", None)
                st.success("Patient ajouté.")
                st.rerun()
            if st.button("← Annuler", key="cancel_new_patient"):
                st.session_state.pop("patient_new", None)
                st.rerun()
        else:
            selected_id = st.session_state.get("selected_patient")
            if selected_id:
                p = db.get_patient(selected_id)
                if not p:
                    st.session_state.pop("selected_patient", None)
                    st.info("Patient introuvable.")
                else:
                    st.markdown(f"### {p['prenom']} {p['nom']}")
                    age = age_from_date(p["date_naissance"])
                    if age:
                        st.caption(f"{age} ans · {p['sexe'] or '—'}")

                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**📍 Adresse**\n{p['adresse'] or '—'}  \n{p['cp'] or ''} {p['commune'] or ''}")
                        st.markdown(f"**📞 Téléphone**\n{p['telephone'] or '—'}")
                    with c2:
                        st.markdown(f"**📧 Email**\n{p['email'] or '—'}")
                        st.markdown(f"**🏥 Mutuelle**\n{p['mutuelle'] or '—'}")
                        st.markdown(f"**🔢 NISS**\n{p['niss'] or '—'}")
                        st.markdown(f"**🔐 Consentement (date d'information)**\n{p.get('consent_date') or '—'}")

                    # Actions rapides (mobile) : appel + itinéraire
                    _adresse = " ".join(filter(None, [p["adresse"], p["cp"], p["commune"]]))
                    _links = _action_links(p["telephone"], _adresse)
                    if _links:
                        st.markdown("   ·   ".join(_links), unsafe_allow_html=True)
                        st.caption(
                            "🔒 RGPD : ouvrir le lien « Itinéraire » transmet l'adresse "
                            "à Google Maps (service tiers) à cet instant-là."
                        )

                    st.markdown(f"**⚠️ Allergies** : {p['allergies'] or 'Aucune'}")
                    st.markdown(f"**💊 Médicaments** : {p['medicaments'] or 'Aucun'}")
                    if p["notes"]:
                        st.markdown(f"**📝 Notes** : {p['notes']}")

                    # Interventions du patient
                    st.divider()
                    st.markdown("**📅 Interventions**")
                    interventions = db.list_interventions(patient_id=p["id"])
                    if interventions:
                        df = pd.DataFrame(interventions)
                        df = df[["date", "heure", "type", "statut", "lieu", "notes"]]
                        df.columns = ["Date", "Heure", "Type", "Statut", "Lieu", "Notes"]
                        st.dataframe(df, width="stretch", hide_index=True)
                    else:
                        st.info("Aucune intervention enregistrée.")

                    st.divider()
                    with st.expander("✏️ Modifier le patient"):
                        data = _patient_form(existing=p, key_prefix=f"edit_{p['id']}")
                        if data:
                            db.update_patient(p["id"], data)
                            st.success("Patient mis à jour.")
                            st.rerun()

                    # Suppression avec confirmation (action irréversible)
                    _confirm_del = f"confirm_del_patient_{p['id']}"
                    if st.session_state.get(_confirm_del):
                        st.warning(
                            "⚠️ Cette action est **irréversible** : le patient et "
                            "toutes ses interventions seront supprimés."
                        )
                        _c_yes, _c_no = st.columns(2)
                        if _c_yes.button("✅ Confirmer la suppression", type="primary",
                                        key=f"confirm_del_yes_{p['id']}", width="stretch"):
                            db.delete_patient(p["id"])
                            st.session_state.pop("selected_patient", None)
                            st.session_state.pop(_confirm_del, None)
                            st.success("Patient supprimé.")
                            st.rerun()
                        if _c_no.button("Annuler", key=f"confirm_del_no_{p['id']}", width="stretch"):
                            st.session_state.pop(_confirm_del, None)
                            st.rerun()
                    elif st.button("🗑️ Supprimer ce patient", key=f"del_{p['id']}"):
                        st.session_state[_confirm_del] = True
                        st.rerun()
            else:
                st.info("Sélectionnez un patient à gauche, ou cliquez sur « ➕ Nouveau patient ».")


# ---------------------------------------------------------------------------
# Page : Agenda / Interventions
# ---------------------------------------------------------------------------
def _interventions_df(rows: list) -> pd.DataFrame:
    """Tableau d'interventions au format affichage (liste et vue semaine)."""
    df = pd.DataFrame(rows)
    df = df[["heure", "prenom", "nom", "type", "statut", "lieu", "duree_min", "notes"]]
    df.columns = ["Heure", "Prénom", "Nom", "Type", "Statut", "Lieu", "Durée (min)", "Notes"]
    df["Patient"] = df.pop("Prénom") + " " + df.pop("Nom")
    return df[["Heure", "Patient", "Type", "Statut", "Lieu", "Durée (min)", "Notes"]]


JOURS_SEMAINE = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def page_agenda():
    st.title("📅 Agenda des interventions")
    st.caption("Planifiez et suivez vos soins, toilettes, pansements et prises de sang")

    patients = db.list_patients()
    if not patients:
        st.warning("Ajoutez d'abord un patient dans l'onglet **Patients**.")
        return

    # Affichage : liste d'un jour ou vue semaine (7 jours)
    vue = st.radio("Affichage", ["📋 Liste du jour", "🗓️ Semaine"],
                   horizontal=True, label_visibility="collapsed")

    # Filtres
    f1, f2, f3 = st.columns(3)
    with f1:
        if vue == "📋 Liste du jour":
            anchor = f1.date_input("Date", value=date.today())
            dates = [anchor.isoformat()]
        else:
            anchor = f1.date_input("Semaine du", value=date.today(),
                                  help="Sélectionne le lundi de la semaine de la date choisie.")
            monday = anchor - timedelta(days=anchor.weekday())
            dates = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    with f2:
        type_filter = f2.selectbox("Type", ["Tous"] + list(db.TYPES_INTERVENTION.keys()))
    with f3:
        statut_filter = f3.selectbox("Statut", ["Tous"] + list(db.STATUTS.keys()))

    date_set = set(dates)
    interventions = [i for i in db.list_interventions() if i["date"] in date_set]
    if type_filter != "Tous":
        interventions = [i for i in interventions if i["type"] == type_filter]
    if statut_filter != "Tous":
        interventions = [i for i in interventions if i["statut"] == statut_filter]

    by_day = {d: [] for d in dates}
    for i in interventions:
        by_day[i["date"]].append(i)

    if vue == "🗓️ Semaine":
        # Vue semaine : un bloc par jour, lundi → dimanche
        for d in dates:
            day = date.fromisoformat(d)
            suffixe = " · aujourd'hui" if d == date.today().isoformat() else ""
            st.markdown(f"**{JOURS_SEMAINE[day.weekday()]} {day.strftime('%d/%m/%Y')}**{suffixe}")
            rows = by_day[d]
            if rows:
                st.dataframe(_interventions_df(rows), width="stretch", hide_index=True,
                             height=min(120 + 35 * len(rows), 400))
            else:
                st.write("")
                st.caption("Aucune intervention")
    elif interventions:
        st.dataframe(_interventions_df(interventions), width="stretch", hide_index=True)
    else:
        st.info("Aucune intervention pour ces critères.")

    st.divider()

    # Formulaire d'ajout
    st.markdown("**➕ Planifier une intervention**")
    with st.form("intervention_form"):
        c1, c2 = st.columns(2)
        with c1:
            patient_id = st.selectbox(
                "Patient",
                patients,
                format_func=lambda p: f"{p['prenom']} {p['nom']} — {p['commune'] or ''}",
            )["id"]
            typ = st.selectbox("Type d'intervention", list(db.TYPES_INTERVENTION.keys()))
        with c2:
            idate = st.date_input("Date", value=date.today())
            heure = st.time_input("Heure", value=datetime.strptime("09:00", "%H:%M").time())
        c3, c4 = st.columns(2)
        with c3:
            duree = st.number_input("Durée (minutes)", min_value=5, max_value=480, value=30, step=5)
        with c4:
            lieu = st.text_input("Lieu", value="Domicile")
        notes = st.text_input("Notes", placeholder="Détails du soin, observations...")
        repeat_weeks = st.number_input(
            "🔁 Répéter sur les N prochaines semaines (0 = une seule fois)",
            min_value=0, max_value=52, value=0, step=1,
            help="Crée la même visite le même jour de la semaine, sur les N semaines suivantes.",
        )
        if st.form_submit_button("📌 Ajouter à l'agenda", width="stretch"):
            created = 0
            for w in range(int(repeat_weeks) + 1):
                d = idate + timedelta(weeks=w)
                db.add_intervention({
                    "patient_id": patient_id,
                    "type": typ,
                    "date": d.isoformat(),
                    "heure": heure.strftime("%H:%M"),
                    "duree_min": int(duree),
                    "statut": "Planifié",
                    "lieu": lieu.strip(),
                    "notes": notes.strip(),
                })
                created += 1
            if created == 1:
                st.success("Intervention planifiée.")
            else:
                st.success(f"{created} interventions planifiées (récurrence hebdomadaire).")
            st.rerun()

    # Gestion des statuts
    st.markdown("**🔄 Mettre à jour le statut**")

    # Suppression d'une intervention : confirmation explicite (irréversible)
    _pending_int = st.session_state.get("pending_int_delete")
    if _pending_int is not None:
        _intv = next((i for i in db.list_interventions() if i["id"] == _pending_int), None)
        if _intv is None:
            st.session_state.pop("pending_int_delete", None)
        else:
            st.warning("⚠️ Cette action est **irréversible** : l'intervention sera supprimée.")
            st.markdown(
                f"{intervention_badge(_intv['type'])}  **{_intv['date']}** · "
                f"{_intv['heure'] or '—'} · {_intv['prenom']} {_intv['nom']}",
                unsafe_allow_html=True,
            )
            _c_yes, _c_no = st.columns(2)
            if _c_yes.button("✅ Confirmer la suppression", type="primary",
                             key="int_del_yes", width="stretch"):
                db.delete_intervention(_pending_int)
                st.session_state.pop("pending_int_delete", None)
                st.success("Intervention supprimée.")
                st.rerun()
            if _c_no.button("Annuler", key="int_del_no", width="stretch"):
                st.session_state.pop("pending_int_delete", None)
                st.rerun()
            st.divider()

    if interventions:
        for row in interventions:
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.markdown(
                f"{row['heure'] or '—'} · {row['prenom']} {row['nom']} · {intervention_badge(row['type'])}",
                unsafe_allow_html=True,
            )
            if c2.button("✅", key=f"st_ok_{row['id']}", help="Marquer comme effectué"):
                db.set_statut(row["id"], "Effectué")
                st.rerun()
            if c3.button("❌", key=f"st_no_{row['id']}", help="Annuler"):
                db.set_statut(row["id"], "Annulé")
                st.rerun()
            if c4.button("🗑️", key=f"st_del_{row['id']}",
                         help="Supprimer (une confirmation sera demandée)"):
                st.session_state["pending_int_delete"] = row["id"]
                st.rerun()


# ---------------------------------------------------------------------------
# Page : Localisation (carte)
# ---------------------------------------------------------------------------
def page_map():
    st.title("🗺️ Localisation des patients")
    st.caption("Carte de la zone d'intervention — La Louvière & communes voisines")

    patients = db.list_patients()
    with_coords = [p for p in patients if p.get("lat") and p.get("lng")]

    if not with_coords:
        st.info(
            "Aucun patient avec coordonnées GPS. "
            "Ajoutez des coordonnées via l'onglet **Patients** (champ lat/lng) ou "
            "utilisez le géocodage automatique ci-dessous."
        )

    # Géocodage simple via Nominatim (OpenStreetMap) — optionnel, sans clé API
    st.markdown("**📍 Géocoder une adresse**")
    with st.form("geocode_form"):
        consent_geo = st.checkbox(
            "✅ J'autorise l'envoi de l'adresse du patient à Nominatim (OpenStreetMap) "
            "pour la géocoder",
            value=False,
            key="geo_consent",
            help="RGPD : l'adresse est transmise au service tiers Nominatim/OSM "
            "uniquement si vous cochez cette case. Sans accord, rien n'est envoyé.",
        )
        gc1, gc2 = st.columns([3, 1])
        patient = gc1.selectbox(
            "Patient",
            patients,
            format_func=lambda p: f"{p['prenom']} {p['nom']}",
        )
        submit = gc2.form_submit_button("🧭 Géocoder l'adresse")
        force = st.checkbox(
            "Re-géocoder même si des coordonnées existent déjà",
            value=False, key="regeo_force",
        )
        if submit and not consent_geo:
            st.warning(
                "🔒 Géocodage non autorisé : cochez la case d'autorisation pour "
                "envoyer l'adresse au service Nominatim (OpenStreetMap)."
            )
        elif submit:
            p = db.get_patient(patient["id"])
            if p.get("lat") and p.get("lng") and not force:
                st.info(
                    f"Ce patient a déjà des coordonnées ({p['lat']:.5f}, {p['lng']:.5f}). "
                    "Cochez « Re-géocoder » pour forcer une nouvelle recherche."
                )
            else:
                query = f"{p['adresse'] or ''} {p['cp'] or ''} {p['commune'] or ''} Belgique".strip()
                if not query:
                    st.warning("Adresse du patient vide — impossible de géocoder.")
                else:
                    _geocode_and_save(p["id"], query)

    # Carte
    if with_coords:
        try:
            import folium
            from streamlit_folium import st_folium  # type: ignore
        except ImportError:
            st.warning(
                "Le paquet `streamlit-folium` est requis pour la carte. "
                "Installez-le avec : `pip install streamlit-folium`"
            )
            return

        # Centre sur La Louvière
        center = [50.4766, 4.3340]
        m = folium.Map(location=center, zoom_start=13)

        # Marqueur de référence (cabinet / centre)
        folium.Marker(
            location=center,
            popup="🏥 Zone — La Louvière",
            icon=folium.Icon(color="green", icon="briefcase", prefix="fa"),
        ).add_to(m)

        today_iso = date.today().isoformat()
        for p in with_coords:
            interventions = db.list_interventions(patient_id=p["id"], date=today_iso)
            active = [i for i in interventions if i["statut"] != "Annulé"]
            # Vert si visite prévue aujourd'hui, gris sinon
            color = "green" if active else "gray"
            # Échappement HTML : les champs proviennent de la base (XSS dans le popup)
            def _esc(v):
                return html.escape(str(v or ""))
            popup = (
                f"<b>{_esc(p['prenom'])} {_esc(p['nom'])}</b><br>"
                f"{_esc(p['adresse'])} {_esc(p['cp'])} {_esc(p['commune'])}<br>"
                f"📞 {_esc(p['telephone']) or '—'}"
            )
            if active:
                visits = " · ".join(_esc(i["heure"]) + " " + _esc(i["type"]).strip() for i in active)
                popup += f"<br>📅 Aujourd'hui : {visits}"
            folium.Marker(
                location=[p["lat"], p["lng"]],
                popup=folium.Popup(popup, max_width=250),
                icon=folium.Icon(color=color, icon="user", prefix="fa"),
            ).add_to(m)

        st_folium(m, width=800, height=500)
        st.caption("Cliquez sur un marqueur pour voir les détails du patient.")
    else:
        st.info("Géocodez au moins un patient pour afficher la carte.")


def _geocode_and_save(patient_id: int, query: str):
    """Géocode une adresse via Nominatim (OpenStreetMap) et enregistre les coordonnées.

    RGPD : l'adresse (donnée personnelle) ne quitte l'application que sur autorisation
    expresse (case à cocher) vers Nominatim. Les journaux et messages d'erreur ne
    contiennent **ni l'adresse ni le nom** — uniquement l'identifiant interne, car
    l'exception réseau brute peut embarquer l'URL (donc l'adresse) en paramètre.
    """
    try:
        import urllib.request
        import json
        url = "https://nominatim.openstreetmap.org/search"
        params = urllib.parse.urlencode({
            "q": query, "format": "json", "limit": 1,
            "countrycodes": "be",
        })
        req = urllib.request.Request(
            f"{url}?{params}",
            headers={"User-Agent": "InfirmiereADomicile/1.4 (application de gestion infirmiere, La Louviere BE)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data:
            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])
            db.update_patient(patient_id, {"lat": lat, "lng": lng})
            logger.info("Géocodage OK (patient %s) : %.5f, %.5f", patient_id, lat, lng)
            st.success(f"Coordonnées trouvées : {lat:.5f}, {lng:.5f}")
            st.rerun()
        else:
            logger.warning("Adresse introuvable lors du géocodage (patient %s).", patient_id)
            st.warning("Adresse introuvable. Vérifiez l'adresse et la commune.")
    except Exception as e:
        # RGPD : on ne journalise ni n'affiche l'exception brute (elle peut contenir
        # l'URL, donc l'adresse du patient) : seul le type d'erreur est consigné.
        logger.warning("Erreur de géocodage (patient %s) : %s", patient_id, type(e).__name__)
        st.error("Erreur de géocodage (réseau ou service OpenStreetMap indisponible).")


# ---------------------------------------------------------------------------
# Page : Facturation (récapitulatif mensuel)
# ---------------------------------------------------------------------------
def page_facturation():
    st.title("💶 Facturation")
    st.caption("Récapitulatif des interventions par patient et par mois — prêt pour la mutuelle")

    now = datetime.now()
    mois_noms = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                 "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    f1, f2 = st.columns([1, 1])
    with f1:
        year = int(f1.number_input("Année", min_value=1990, max_value=2100,
                                  value=now.year, step=1,
                                  help="Période facturée (1990 à 2100)."))
    with f2:
        month = int(f2.selectbox("Mois", list(range(1, 13)), index=now.month - 1,
                                 format_func=lambda m: mois_noms[m - 1]))

    include_planned = st.checkbox(
        "Inclure les interventions planifiées (non encore réalisées)",
        value=False,
        help="Par défaut, seules les interventions « Effectué » sont comptabilisées. "
             "Cochez pour inclure aussi celles encore « Planifié ».",
    )

    rows = db.billing_summary(year, month, include_planned=include_planned)

    if not rows:
        st.info(
            "Aucune intervention effectuée enregistrée pour ce mois "
            "(cochez « Inclure les interventions planifiées » pour élargir)."
        )
        return

    types = list(db.TYPES_INTERVENTION.keys())
    records = []
    for r in rows:
        rec = {
            "Prénom": r["prenom"],
            "Nom": r["nom"],
            "NISS": r["niss"],
            "Commune": r["commune"],
            "Mutuelle": r["mutuelle"],
        }
        for t in types:
            rec[t] = r["types"].get(t, 0)
        rec["Total"] = r["total"]
        records.append(rec)

    df = pd.DataFrame(records)
    df = df[["Prénom", "Nom", "NISS", "Commune", "Mutuelle"] + types + ["Total"]]
    st.dataframe(df, width="stretch", hide_index=True)

    total_general = int(df["Total"].sum())
    st.markdown(f"**Total du mois : {total_general} intervention(s) — {len(rows)} patient(s)**")

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Exporter en CSV (Excel)",
        data=csv,
        file_name=f"facturation_{year}_{month:02d}.csv",
        mime="text/csv",
    )

    # Export PDF (prêt à envoyer / archiver)
    try:
        pdf = _billing_pdf(year, month, records, types, total_general, len(rows))
        st.download_button(
            "🖨️ Télécharger le PDF",
            data=pdf,
            file_name=f"facturation_{year}_{month:02d}.pdf",
            mime="application/pdf",
        )
    except ImportError:
        st.warning(
            "Le paquet `reportlab` est requis pour l'export PDF. "
            "Installez-le avec : `pip install reportlab`"
        )


def _billing_pdf(year, month, records, types, total_general, n_patients):
    """Génère un PDF A4 paysage du récapitulatif de facturation."""
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    mois_noms = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                 "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title=f"Facturation {mois_noms[month - 1]} {year}",
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"Récapitulatif de facturation — {mois_noms[month - 1]} {year}", styles["Title"]),
        Paragraph(
            f"Infirmière à Domicile — La Louvière · {n_patients} patient(s) · "
            f"{total_general} intervention(s) au total",
            styles["Normal"],
        ),
        Spacer(1, 0.5 * cm),
    ]
    header = ["Prénom", "Nom", "NISS", "Commune", "Mutuelle"] + types + ["Total"]
    data = [header] + [[rec[h] for h in header] for rec in records]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eff6ff")]),
    ]))
    doc.build(elements + [table])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# CSS global (thème moderne) + CSS mobile (touch-friendly, responsive)
# Les couleurs de base sont aussi définies dans `.streamlit/config.toml` ;
# ce bloc ajoute les finitions (cartes, boutons, arrondis, tactiles).
# ---------------------------------------------------------------------------
def inject_mobile_css():
    st.markdown(
        """
        <style>
        /* ---------- Modernisation (toutes tailles) ---------- */
        * { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
            text-rendering: optimizeLegibility; }

        .block-container { max-width: 1200px; }

        /* Boutons plus doux, retour visuel au survol / appui */
        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
            border-radius: 10px;
            transition: background-color 0.15s ease, box-shadow 0.15s ease, transform 0.05s ease;
        }
        .stButton > button:hover { box-shadow: 0 2px 10px rgba(37, 99, 235, 0.18); }
        .stButton > button:active, .stFormSubmitButton > button:active { transform: translateY(1px); }

        /* Cartes de métriques du tableau de bord */
        [data-testid="stMetric"] {
            border: 1px solid rgba(37, 99, 235, 0.14);
            border-radius: 14px;
            background: linear-gradient(135deg, rgba(37, 99, 235, 0.06), rgba(37, 99, 235, 0.01));
            padding: 12px 16px;
        }

        /* Formulaires, panneaux et tableaux plus modernes */
        .stForm {
            border-radius: 14px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 4px rgba(15, 23, 42, 0.05);
        }
        [data-testid="stExpander"] section { border-radius: 12px; border-color: #e2e8f0; }
        [data-testid="stDataFrame"] { border-radius: 12px; }

        /* Barre latérale légèrement teintée */
        [data-testid="stSidebar"] { background: #f8fafc; }

        /* Liens d'action plus tapables (toutes tailles) */
        [data-testid="stMarkdownContainer"] a { text-decoration: none; }

        /* ---------- Mobile-first : cibles tactiles + lisibilité ---------- */
        @media (max-width: 768px) {
            .block-container {
                padding-top: 1.25rem;
                padding-left: 0.75rem;
                padding-right: 0.75rem;
                padding-bottom: 3rem;
                max-width: 100%;
            }
            /* Empiler les colonnes pour une lecture verticale */
            .st-columns { flex-direction: column !important; row-gap: 0.5rem; }
            .st-columns > div { width: 100% !important; }
            /* Gros boutons tactiles (>= 48px) */
            .stButton > button, .stFormSubmitButton > button {
                min-height: 48px;
                font-size: 1.05rem;
                padding: 0.7rem 1rem;
                border-radius: 12px;
            }
            /* Titres compacts */
            h1 { font-size: 1.55rem; }
            h2 { font-size: 1.25rem; }
            h3 { font-size: 1.1rem; }
            h4 { font-size: 1.02rem; }
            /* Champs de formulaire plus grands */
            .stTextInput input, .stTextArea textarea, .stNumberInput input,
            .stDateInput input, .stTimeInput input {
                font-size: 1rem;
                min-height: 44px;
            }
            /* Tableaux plus lisibles */
            [data-testid="stDataFrame"] { font-size: 0.95rem; }
            /* Sidebar mobile quasi pleine largeur */
            [data-testid="stSidebar"] { min-width: 88vw; }
            /* Badge d'intervention : plus grand sur mobile */
            [data-testid="stMarkdownContainer"] span {
                font-size: 0.9rem !important;
                padding: 4px 12px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page : Aujourd'hui (vue mobile-first — l'écran principal sur le terrain)
# ---------------------------------------------------------------------------
def _maps_directions_url(adresse: str) -> str:
    """Lien Google Maps « itinéraire » vers une adresse (Belgique)."""
    q = urllib.parse.quote((adresse + " Belgique").strip())
    return f"https://www.google.com/maps/dir/?api=1&destination={q}"


def _action_links(tel: str, adresse: str):
    """Renvoie la liste des liens d'action (appel + itinéraire) pour un patient."""
    links = []
    tel_clean = (tel or "").replace(" ", "").replace(".", "")
    if tel_clean:
        links.append(f"[📞 Appeler](tel:{tel_clean})")
    if adresse:
        links.append(f"[🧭 Itinéraire]({_maps_directions_url(adresse)})")
    return links


def page_today():
    st.title("📱 Aujourd'hui")
    st.caption("Vos visites du jour — appel, itinéraire et validation en un tap")

    today = date.today().isoformat()
    interventions = sorted(
        db.list_interventions(date=today),
        key=lambda i: (i["heure"] or "99:99"),
    )
    total = len(interventions)
    done = sum(1 for i in interventions if i["statut"] == "Effectué")
    if total:
        st.progress(done / total, text=f"{done}/{total} interventions effectuées")

    if not total:
        st.success("Aucune intervention prévue aujourd'hui. 🎉")
        return

    for i in interventions:
        name = f"{i['prenom']} {i['nom']}"
        heure = i["heure"] or "—"
        adresse = " ".join(filter(None, [i["adresse"], i["cp"], i["commune"]]))
        tel = i["telephone"] or ""
        statut = i["statut"]

        # En-tête de la visite
        st.markdown(f"#### {heure} — {name}")
        st.markdown(intervention_badge(i["type"]), unsafe_allow_html=True)
        if i["notes"]:
            st.caption(f"📝 {i['notes']}")
        if adresse:
            st.markdown(f"📍 {adresse}")

        # Actions rapides (mobile) : appel + itinéraire
        links = _action_links(tel, adresse)
        if links:
            st.markdown("   ·   ".join(links), unsafe_allow_html=True)
            st.caption(
                "🔒 RGPD : ouvrir le lien « Itinéraire » transmet l'adresse "
                "à Google Maps (service tiers) à cet instant-là."
            )

        # Validation du statut
        if statut == "Planifié":
            b1, b2 = st.columns(2)
            if b1.button("✅ Effectué", key=f"today_ok_{i['id']}", type="primary", width="stretch"):
                db.set_statut(i["id"], "Effectué")
                st.rerun()
            if b2.button("❌ Annulé", key=f"today_no_{i['id']}", width="stretch"):
                db.set_statut(i["id"], "Annulé")
                st.rerun()
        else:
            st.markdown(f"Statut : **{statut}**")
        st.divider()


# ---------------------------------------------------------------------------
# Page : Confidentialité (RGPD)
# ---------------------------------------------------------------------------
def page_privacy():
    st.title("🔐 Confidentialité & RGPD")
    st.caption(
        "Comment vos données sont traitées, protégées et exploitées dans cette application"
    )

    st.markdown("### 🏛️ Responsable du traitement")
    st.markdown(
        "L'utilisation de cette application est le fait de **l'utilisatrice** "
        "(l'infirmière à domicile) : elle est responsable du traitement des "
        "données de ses patients dans le cadre de son activité "
        "(RGPD, art. 4.7 — « responsable du traitement »)."
    )

    st.markdown("### 📋 Données traitées")
    st.markdown(
        "- **Identité** : prénom, nom, date de naissance, sexe\n"
        "- **Coordonnées** : adresse, code postal, commune, téléphone, email, mutuelle\n"
        "- **NISS** (n° de sécurité sociale, pour la facturation)\n"
        "- **Données de santé** (art. 9 RGPD — catégorie *spéciale*) : allergies, "
        "médicaments, notes cliniques, interventions\n"
        "- **Coordonnées GPS** : uniquement si un géocodage a été autorisé\n"
        "- **Consentement** : date d'information du patient (art. 13-14)"
    )

    st.markdown("### 🎯 Finalités du traitement")
    st.markdown(
        "Gestion de l'activité de soins à domicile : planification des "
        "interventions, suivi des patients, facturation (NISS, mutuelle) et "
        "localisation des visites. Aucune vente de données, aucun profilage, "
        "**aucune télémétrie** (les statistiques d'usage Streamlit sont "
        "désactivées — `gatherUsageStats=false`)."
    )

    st.markdown("### 🤝 Sous-traitants (services tiers)")
    st.markdown(
        "| Service | Quand | Données transmises |\n"
        "|---|---|---|\n"
        "| **Nominatim (OpenStreetMap)** | uniquement si vous cochez la case "
        "d'autorisation dans « Localisation » | l'adresse à géocoder |\n"
        "| **Google Maps** | uniquement au clic sur le lien « Itinéraire » | "
        "l'adresse (dans l'URL du lien) |\n"
        "| *Aucun autre* | — | le reste est **100 % local** (fichier SQLite sur "
        "cet appareil) |"
    )

    st.markdown("### 🗄️ Durée de conservation (rétention)")
    st.markdown(
        "- Les données restent sur l'appareil tant que vous ne supprimez pas "
        "le fichier `data/infirmiere.db` (suppression = droit à l'effacement).\n"
        "- **5 sauvegardes** récentes maximum sont conservées automatiquement ; "
        "les plus anciennes sont supprimées (pensez à les téléverser sur un "
        "support externe si vous souhaitez les garder)."
    )

    st.markdown("### ✅ Vos droits (RGPD art. 15-21)")
    st.markdown(
        "- **Accès / portabilité** (art. 15, 20) : export CSV de la liste des "
        "patients et de la facturation (boutons ⬇️ dans l'app).\n"
        "- **Rectification** (art. 16) : formulaire « ✏️ Modifier le patient ».\n"
        "- **Effacement** (art. 17) : « 🗑️ Supprimer ce patient » — confirmation "
        "explicite requise, action irréversible."
    )

    st.markdown("### 🔒 Mesures de sécurité (art. 32)")
    st.markdown(
        "- Base **SQLite locale** : aucun serveur distant, aucune dépendance "
        "obligatoire en ligne ;\n"
        "- Mot de passe haché **PBKDF2-SHA256 — 600 000 itérations + sel** "
        "(recommandation OWASP 2023), jamais stocké en clair ;\n"
        "- **Verrouillage anti brute-force** : 5 tentatives échouées → 30 s de "
        "blocage de connexion ;\n"
        "- **Fuites de données limitées** : le fichier temporaire de restauration "
        "est supprimé après usage, les journaux ne contiennent **ni nom, ni "
        "adresse, ni téléphone** (seul l'identifiant interne est consigné), "
        "les popups carte sont échappés contre le XSS ;\n"
        "- **Docker** : utilisateur non-root, données isolées dans `/data` ;\n"
        "- **HTTPS recommandé** pour tout accès distant (tunnel ou hébergement)."
    )

    st.markdown("### 🧪 Données de démonstration")
    st.markdown(
        "Par défaut, l'application démarre avec une base **vide** : les "
        "patients d'exemple (personnes fictives avec des données de santé) ne "
        "sont créés que si vous le demandez explicitement au lancement :\n\n"
        "```bash\n"
        "NURSE_SEED_DEMO=1 streamlit run app.py\n"
        "```"
    )

    st.markdown("### ⚠️ Bonnes pratiques")
    st.markdown(
        "- Définissez un **mot de passe** (barre latérale) avant tout usage ;\n"
        "- Sauvegardez régulièrement (barre latérale) et conservez les "
        "sauvegardes en lieu sûr ;\n"
        "- N'exposez pas l'application publiquement sans HTTPS et sans mot de "
        "passe ;\n"
        "- Les liens « Itinéraire » et le géocodage transmettent l'adresse à un "
        "service tiers **au moment de l'action uniquement** — ne les utilisez "
        "que si le patient en a été informé (art. 13-14)."
    )

    st.divider()
    st.caption(
        f"Infirmière à Domicile v{VERSION} — questions ou réclamations : "
        "contactez la responsable du traitement (l'utilisatrice de l'app)."
    )


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
def _require_auth() -> bool:
    """Porte d'entrée : écran de connexion si un mot de passe est défini.

    - Aucun mot de passe défini → l'app reste accessible (mode local simple).
    - Mot de passe défini → connexion requise avant d'afficher l'app.

    Renvoie ``True`` si l'app est autorisée à continuer ; sinon ``main()``
    s'arrête juste après l'écran de connexion (``st.stop()``), de sorte que
    ni la navigation ni les données ne sont rendues.
    """
    if not auth.password_is_set():
        return True
    if st.session_state.get("authenticated"):
        return True

    st.title("🔒 Connexion")
    st.caption("Infirmière à Domicile — Wallonie (La Louvière)")
    with st.form("login_form"):
        pwd = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Se connecter", type="primary", width="stretch"):
            if auth.verify_password(pwd):
                st.session_state["authenticated"] = True
                logger.info("Connexion réussie.")
                st.rerun()
                return True
            _msg = "Mot de passe incorrect."
            _wait = auth.lockout_remaining()
            if _wait > 0:
                _msg += f" Plus de tentatives possibles pendant {_wait} s (verrouillage anti brute-force)."
            st.error(_msg)
    return False


def main():
    if not _require_auth():
        st.stop()
    inject_mobile_css()

    st.sidebar.markdown("## 🩺 Infirmière à Domicile")
    st.sidebar.caption(f"Wallonie — La Louvière · v{VERSION}")
    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["📱 Aujourd'hui", "📊 Tableau de bord", "👥 Patients", "📅 Agenda",
         "💶 Facturation", "🗺️ Localisation", "🔐 Confidentialité"],
    )

    st.sidebar.divider()
    st.sidebar.markdown("**Zone d'intervention**")
    st.sidebar.caption(
        "La Louvière · Châtelineau · Boussu · Hornu · Morlanwelz · Quaregnon"
    )
    st.sidebar.divider()
    st.sidebar.markdown("**💾 Sauvegarde**")
    if st.sidebar.button("💾 Créer une sauvegarde", key="btn_backup"):
        st.session_state["backup_path"] = db.backup()
        db.prune_backups(keep=5)  # rétention : ne garder que les 5 dernières
    bp = st.session_state.get("backup_path")
    if bp and os.path.exists(bp):
        with open(bp, "rb") as _f:
            _data = _f.read()
        st.sidebar.download_button(
            "⬇️ Télécharger", data=_data,
            file_name=os.path.basename(bp), mime="application/octet-stream",
        )
    uploaded = st.sidebar.file_uploader("♻️ Restaurer une sauvegarde", type=["db"], key="restore_up")
    if uploaded is not None:
        if st.sidebar.button("Confirmer la restauration", key="btn_restore"):
            tmp = os.path.join(tempfile.gettempdir(), "restore_infirmiere.db")
            try:
                with open(tmp, "wb") as _f:
                    _f.write(uploaded.getvalue())
                try:
                    os.chmod(tmp, 0o600)  # accès restreint (meilleur effort)
                except OSError:
                    pass  # OS sans support chmod (rare sous Windows)
                safety = db.backup()  # filet de sécurité avant tout écrasement
                db.restore(tmp)
            finally:
                try:
                    os.remove(tmp)  # RGPD : ne pas laisser les données patients en temp
                except OSError:
                    pass
            st.sidebar.success(
                f"Base restaurée. Sauvegarde de sécurité : {os.path.basename(safety)}"
            )
            st.rerun()
    st.sidebar.divider()
    if st.sidebar.button("🔓 Se déconnecter", key="btn_logout", use_container_width=True):
        st.session_state.pop("authenticated", None)
        st.rerun()
    if auth.password_is_set():
        st.sidebar.caption("🔒 Session protégée par mot de passe.")
    else:
        st.sidebar.caption(
            "⚠️ Aucun mot de passe défini : l'application est accessible à quiconque peut "
            "ouvrir le port 8501. Définissez-en un ci-dessous pour la protéger."
        )
        with st.sidebar.expander("🔑 Définir un mot de passe"):
            with st.form("setup_pwd_form"):
                p1 = st.text_input("Nouveau mot de passe (min. 4 caractères)", type="password")
                p2 = st.text_input("Confirmer", type="password")
                if st.form_submit_button("Définir le mot de passe", width="stretch"):
                    if p1 != p2:
                        st.error("Les deux mots de passe ne correspondent pas.")
                    elif len(p1) < 4:
                        st.error("Le mot de passe doit contenir au moins 4 caractères.")
                    else:
                        auth.set_password(p1)
                        st.session_state.pop("authenticated", None)
                        st.success("Mot de passe défini.")
                        st.rerun()
    st.sidebar.divider()
    st.sidebar.caption("© 2026 — Application de gestion de soins à domicile")

    if page.startswith("📱"):
        page_today()
    elif page.startswith("📊"):
        page_dashboard()
    elif page.startswith("👥"):
        page_patients()
    elif page.startswith("📅"):
        page_agenda()
    elif page.startswith("💶"):
        page_facturation()
    elif page.startswith("🗺️"):
        page_map()
    elif page.startswith("🔐"):
        page_privacy()


if __name__ == "__main__":
    main()
