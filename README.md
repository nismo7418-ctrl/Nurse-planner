# 🩺 Infirmière à Domicile — Wallonie (La Louvière)

Application web de gestion pour une infirmière à domicile, basée sur **Python + Streamlit**.
Elle permet de gérer les **patients**, les **soins** (soins, toilette, pansement, prise de sang,
injection, surveillance) et la **localisation** des patients sur une carte.

## ✨ Fonctionnalités

- **📊 Tableau de bord** — statistiques, interventions du jour, actions rapides (Effectué / Annulé).
- **👥 Patients** — ajout, recherche, modification, suppression ; coordonnées, mutuelle,
  allergies, médicaments, notes ; historique des interventions.
- **📅 Agenda** — planification des interventions par date, type et statut ; suivi du statut.
- **🗺️ Localisation** — carte interactive (Leaflet/OpenStreetMap) centrée sur La Louvière,
  avec géocodage automatique des adresses (Nominatim, sans clé API).

## 📁 Structure

```
Nurse planer/
├── app.py            # Application Streamlit (interface)
├── database.py       # Couche de données (SQLite)
├── requirements.txt  # Dépendances Python
├── README.md
└── data/             # Base de données SQLite (créée automatiquement)
    └── infirmiere.db
```

## 🚀 Installation & lancement

1. Installez Python 3.9+ puis les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

2. Lancez l'application :

   ```bash
   streamlit run app.py
   ```

3. Ouvrez le navigateur sur `http://localhost:8501`.

> La base de données SQLite est créée automatiquement au premier lancement,
> avec quelques patients et interventions d'exemple dans la zone de La Louvière.

## 🗺️ Localisation

- Les patients d'exemple ont déjà des coordonnées GPS (La Louvière, Châtelineau).
- Pour géocoder une adresse, utilisez l'onglet **Localisation** → « Géocoder l'adresse ».
  Le géocodage utilise OpenStreetMap (Nominatim) et nécessite une connexion internet.

## 📝 Notes

- Les données sont stockées localement dans `data/infirmiere.db` (aucun serveur distant).
- Pour repartir de zéro, supprimez simplement le fichier `data/infirmiere.db`.
