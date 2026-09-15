"""
🩺 Infirmière à Domicile — Wallonie (La Louvière)
Application Streamlit de gestion des patients, des soins et de la localisation.

Lancement :
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime

import database as db

# ---------------------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Infirmière à Domicile — La Louvière",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialisation de la base de données
db.init_db()

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


def patient_label(p):
    return f"{p['prenom']} {p['nom']}"


def intervention_badge(typ):
    color = TYPE_COLORS.get(typ, "#6b7280")
    return (
        f"<span style='background:{color};color:white;padding:2px 10px;"
        f"border-radius:12px;font-size:0.8rem;font-weight:600'>{typ}</span>"
    )


def statut_badge(statut):
    colors = {"Planifié": "#2563eb", "Effectué": "#059669", "Annulé": "#dc2626"}
    color = colors.get(statut, "#6b7280")
    return (
        f"<span style='background:{color}22;color:{color};border:1px solid {color};"
        f"padding:2px 10px;border-radius:12px;font-size:0.8rem;font-weight:600'>{statut}</span>"
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
    c3.metric("✅ Effectuées", s["effectuees"])
    c4.metric("🕒 Planifiées", s["planifiees"])

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
        if not prenom.strip() or not nom.strip():
            st.error("Le prénom et le nom sont obligatoires.")
            return None

        return {
            "nom": nom.strip(),
            "prenom": prenom.strip(),
            "date_naissance": date_naissance.isoformat() if date_naissance else "",
            "sexe": sexe,
            "adresse": adresse.strip(),
            "cp": cp.strip(),
            "commune": commune.strip(),
            "telephone": telephone.strip(),
            "email": email.strip(),
            "mutuelle": mutuelle.strip(),
            "allergies": allergies.strip(),
            "medicaments": medicaments.strip(),
            "notes": notes.strip(),
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

    with right:
        selected_id = st.session_state.get("selected_patient")
        if selected_id:
            p = db.get_patient(selected_id)
            if p:
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

                if st.button("🗑️ Supprimer ce patient", key=f"del_{p['id']}"):
                    db.delete_patient(p["id"])
                    st.session_state.pop("selected_patient", None)
                    st.success("Patient supprimé.")
                    st.rerun()
        else:
            st.markdown("**➕ Nouveau patient**")
            data = _patient_form(key_prefix="new")
            if data:
                new_id = db.add_patient(data)
                st.session_state["selected_patient"] = new_id
                st.success("Patient ajouté.")
                st.rerun()


# ---------------------------------------------------------------------------
# Page : Agenda / Interventions
# ---------------------------------------------------------------------------
def page_agenda():
    st.title("📅 Agenda des interventions")
    st.caption("Planifiez et suivez vos soins, toilettes, pansements et prises de sang")

    patients = db.list_patients()
    if not patients:
        st.warning("Ajoutez d'abord un patient dans l'onglet **Patients**.")
        return

    # Filtres
    f1, f2, f3 = st.columns(3)
    with f1:
        date_filter = f1.date_input("Date", value=date.today())
    with f2:
        type_filter = f2.selectbox("Type", ["Tous"] + list(db.TYPES_INTERVENTION.keys()))
    with f3:
        statut_filter = f3.selectbox("Statut", ["Tous"] + list(db.STATUTS.keys()))

    interventions = db.list_interventions(date=date_filter.isoformat())
    if type_filter != "Tous":
        interventions = [i for i in interventions if i["type"] == type_filter]
    if statut_filter != "Tous":
        interventions = [i for i in interventions if i["statut"] == statut_filter]

    # Tableau
    if interventions:
        df = pd.DataFrame(interventions)
        df = df[["heure", "prenom", "nom", "type", "statut", "lieu", "duree_min", "notes"]]
        df.columns = ["Heure", "Prénom", "Nom", "Type", "Statut", "Lieu", "Durée (min)", "Notes"]
        df["Patient"] = df.pop("Prénom") + " " + df.pop("Nom")
        df = df[["Heure", "Patient", "Type", "Statut", "Lieu", "Durée (min)", "Notes"]]
        st.dataframe(df, width="stretch", hide_index=True)
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
        if st.form_submit_button("📌 Ajouter à l'agenda", width="stretch"):
            db.add_intervention({
                "patient_id": patient_id,
                "type": typ,
                "date": idate.isoformat(),
                "heure": heure.strftime("%H:%M"),
                "duree_min": int(duree),
                "statut": "Planifié",
                "lieu": lieu.strip(),
                "notes": notes.strip(),
            })
            st.success("Intervention planifiée.")
            st.rerun()

    # Gestion des statuts
    st.markdown("**🔄 Mettre à jour le statut**")
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
            if c4.button("🗑️", key=f"st_del_{row['id']}", help="Supprimer"):
                db.delete_intervention(row["id"])
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
        gc1, gc2 = st.columns([3, 1])
        patient = gc1.selectbox(
            "Patient",
            patients,
            format_func=lambda p: f"{p['prenom']} {p['nom']}",
        )
        submit = gc2.form_submit_button("🧭 Géocoder l'adresse")
        if submit:
            p = db.get_patient(patient["id"])
            query = f"{p['adresse'] or ''} {p['cp'] or ''} {p['commune'] or ''} Belgique".strip()
            if query:
                try:
                    import urllib.parse
                    import urllib.request
                    import json
                    url = "https://nominatim.openstreetmap.org/search"
                    params = urllib.parse.urlencode({
                        "q": query, "format": "json", "limit": 1,
                        "countrycodes": "be",
                    })
                    req = urllib.request.Request(
                        f"{url}?{params}",
                        headers={"User-Agent": "InfirmiereApp/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode())
                    if data:
                        lat = float(data[0]["lat"])
                        lng = float(data[0]["lon"])
                        db.update_patient(p["id"], {"lat": lat, "lng": lng})
                        st.success(f"Coordonnées trouvées : {lat:.5f}, {lng:.5f}")
                        st.rerun()
                    else:
                        st.warning("Adresse introuvable. Vérifiez l'adresse et la commune.")
                except Exception as e:
                    st.error(f"Erreur de géocodage : {e}")

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

        for p in with_coords:
            color = "red"
            # Couleur selon le type d'intervention du jour
            interventions = db.list_interventions(patient_id=p["id"], date=date.today().isoformat())
            if interventions:
                typ = interventions[0]["type"]
                color = {
                    "Soins": "blue", "Toilette": "lightblue", "Pansement": "orange",
                    "Prise de sang": "red", "Injection": "purple", "Surveillance": "green",
                }.get(typ, "red")
            popup = (
                f"<b>{p['prenom']} {p['nom']}</b><br>"
                f"{p['adresse'] or ''} {p['cp'] or ''} {p['commune'] or ''}<br>"
                f"📞 {p['telephone'] or '—'}"
            )
            folium.Marker(
                location=[p["lat"], p["lng"]],
                popup=folium.Popup(popup, max_width=250),
                icon=folium.Icon(color=color, icon="user", prefix="fa"),
            ).add_to(m)

        st_folium(m, width=800, height=500)
        st.caption("Cliquez sur un marqueur pour voir les détails du patient.")
    else:
        st.info("Géocodez au moins un patient pour afficher la carte.")


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
def main():
    st.sidebar.markdown("## 🩺 Infirmière à Domicile")
    st.sidebar.caption("Wallonie — La Louvière")
    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["📊 Tableau de bord", "👥 Patients", "📅 Agenda", "🗺️ Localisation"],
    )

    st.sidebar.divider()
    st.sidebar.markdown("**Zone d'intervention**")
    st.sidebar.caption(
        "La Louvière · Châtelineau · Boussu · Hornu · Morlanwelz · Quaregnon"
    )
    st.sidebar.divider()
    st.sidebar.caption("© 2026 — Application de gestion de soins à domicile")

    if page.startswith("📊"):
        page_dashboard()
    elif page.startswith("👥"):
        page_patients()
    elif page.startswith("📅"):
        page_agenda()
    elif page.startswith("🗺️"):
        page_map()


if __name__ == "__main__":
    main()
