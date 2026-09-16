# 🩺 Infirmière à Domicile — Wallonie (La Louvière)

Application web de gestion pour une infirmière à domicile, basée sur **Python + Streamlit**.
Elle permet de gérer les **patients**, les **soins** (soins, toilette, pansement, prise de sang,
injection, surveillance) et la **localisation** des patients sur une carte.

## ✨ Fonctionnalités

- **📱 Aujourd'hui** — vue **mobile-first** : la liste des visites du jour triées par heure,
  avec **appel en 1 tap** (`tel:`), **itinéraire Google Maps** et gros boutons
  « ✅ Effectué » / « ❌ Annulé ». C'est l'écran principal sur le terrain.
- **📊 Tableau de bord** — statistiques du jour, interventions du jour, actions rapides (Effectué / Annulé).
- **👥 Patients** — ajout, recherche, modification, suppression **avec confirmation** ;
  coordonnées, **NISS**, mutuelle, allergies, médicaments, notes ; historique des
  interventions. **Validation des saisies non bloquante** : toutes les erreurs sont
  listées d'un coup (date non future, email, téléphone 8–13 chiffres) et **export CSV**
  de la liste des patients.
- **📅 Agenda** — planification des interventions par date, type et statut ; **récurrence hebdomadaire**
  (répéter une visite sur N semaines) ; suivi du statut ; suppression **avec confirmation**.
- **💶 Facturation** — récapitulatif mensuel des interventions par patient (par type),
  avec NISS et mutuelle, sur la période **1990 à 2100**. **Option « Inclure les interventions
  planifiées »** (désactivée par défaut : seules les visites « Effectué » sont comptées)
  et **export CSV/Excel + PDF** prêt à envoyer / archiver.
- **🗺️ Localisation** — carte interactive (Leaflet/OpenStreetMap) centrée sur La Louvière,
  avec géocodage des adresses (Nominatim, sans clé API) **sur autorisation explicite** (case
  RGPD dans le formulaire) et **cache des coordonnées** (pas de re-géocodage si déjà
  présentes, forçable via une case à cocher) ; patients à visiter aujourd'hui en vert.
- **🔐 Confidentialité** — page dédiée au RGPD : responsable du traitement, données
  traitées, sous-traitants, rétention, droits (accès/rectification/effacement),
  mesures de sécurité (art. 32) et bonnes pratiques.
- **💾 Sauvegarde** — création d'une sauvegarde horodatée de la base, téléchargement et
  restauration depuis un fichier, avec **sauvegarde automatique avant toute restauration**.

## 📁 Structure

```
Nurse-planner/
├── app.py            # Application Streamlit (interface)
├── auth.py           # Authentification locale (PBKDF2, sans dépendance externe)
├── database.py       # Couche de données (SQLite)
├── tests/            # Suite pytest (base temporaire, jamais la vraie DB)
├── manifest.json     # Manifeste PWA (installation sur l'écran d'accueil)
├── .streamlit/config.toml  # Thème (couleurs, police) appliqué automatiquement
├── icons/            # Icônes de l'app (192/512 px + favicon)
├── requirements.txt  # Dépendances Python
├── pyproject.toml    # Métadonnées projet + configuration Ruff & pytest
├── Dockerfile        # Image Docker (non-root, healthcheck, /data)
├── .dockerignore
├── .editorconfig     # Convention d'indentation / encodage
├── .github/workflows/ci.yml  # CI : lint + tests
├── .gitignore        # Exclut __pycache__ et la base de données du dépôt
├── README.md
└── data/             # Base de données SQLite (créée automatiquement, non versionnée)
    └── infirmiere.db
```

## 🚀 Installation & lancement

1. Installez Python 3.9+ puis les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

   > L'application utilise des fonctionnalités récentes de Streamlit
   > (`width="stretch"`) : **Streamlit ≥ 1.49** est requis (déjà précisé dans
   > `requirements.txt`).
   >
   > L'export **PDF** de la facturation utilise `reportlab` (déjà dans `requirements.txt`).
   > Sans ce paquet, l'application fonctionne mais affiche un avertissement et masque
   > le bouton « Télécharger le PDF ».

2. Lancez l'application :

   ```bash
   streamlit run app.py
   ```

3. Ouvrez le navigateur sur `http://localhost:8501`.

> La base de données SQLite est créée automatiquement au premier lancement,
> **vide** (RGPD : aucune personne fictive n'est créée sans votre accord).
> Pour charger des patients et interventions d'exemple (zone de La Louvière),
> lancez explicitement :
>
> ```bash
> NURSE_SEED_DEMO=1 streamlit run app.py
> ```

## 🗺️ Localisation

- Les patients d'exemple (chargés avec `NURSE_SEED_DEMO=1`) ont déjà des
  coordonnées GPS (La Louvière, Châtelineau).
- Pour géocoder une adresse, utilisez l'onglet **Localisation** → « Géocoder l'adresse ».
  Le géocodage utilise OpenStreetMap (Nominatim) et nécessite une connexion internet.
- **RGPD** : l'envoi de l'adresse à Nominatim est conditionné par une **case
  d'autorisation** cochée dans le formulaire — sans accord, rien n'est envoyé.
  Les liens « Itinéraire » transmettent l'adresse à Google Maps **uniquement au
  clic** (un rappel RGPD s'affiche à côté des liens).

## 💾 Sauvegarde & restauration

- Dans la barre latérale, **« 💾 Créer une sauvegarde »** copie la base dans
  `data/infirmiere_backup_<date>.db` et propose le téléchargement.
- **Rétention automatique** : seules les 5 sauvegardes les plus récentes sont
  conservées dans `data/` (les plus anciennes sont supprimées automatiquement).
  Téléchargez-les sur un support externe si vous souhaitez garder plus longtemps.
- **« ♻️ Restaurer une sauvegarde »** permet de réimporter un fichier `.db` de sauvegarde
  (une sauvegarde de sécurité est créée juste avant l'écrasement).

## 📱 Utilisation sur téléphone

L'application est **optimisée mobile** (cibles tactiles ≥ 48 px, colonnes empilées,
textes lisibles, tableaux adaptés). La page **📱 Aujourd'hui** est conçue pour être
utilisée sur le terrain : appel du patient, itinéraire et validation en un tap.

### Accéder depuis le téléphone (même Wi-Fi)

1. Sur l'ordinateur, lancez l'app puis ouvrez un terminal :
   ```bash
   # Adresse IP locale de l'ordinateur (Windows)
   ipconfig
   ```
2. Sur le téléphone (même réseau Wi-Fi), ouvrez le navigateur sur :
   ```
   http://<IP-LOCALE>:8501
   ```
   (ex. `http://192.168.1.20:8501`).

> 💡 Pour que Streamlit accepte les connexions distantes, lancez-le avec :
> ```bash
> streamlit run app.py --server.address 0.0.0.0
> ```

### 📲 Installer sur l'écran d'accueil (PWA)

L'app embarque un **manifeste PWA** (`manifest.json`) et une icône (`icons/`).
Pour pouvoir « **Ajouter à l'écran d'accueil** » avec une icône et un mode plein écran,
le navigateur exige un accès en **HTTPS** (l'installation PWA est bloquée en HTTP
simple sur réseau local).

Options pour obtenir du HTTPS :
- **Tunnel gratuit** (le plus simple) : `cloudflared tunnel --url http://localhost:8501`
  ou `ngrok http 8501` — vous obtenez une URL `https://…` à ouvrir sur le téléphone,
  puis « Ajouter à l'écran d'accueil ».
- **Hébergement** : déployer l'app sur un service avec HTTPS (ex. Streamlit Community
  Cloud, Render, Fly.io) et y accéder depuis le téléphone.

> ⚠️ **RGPD** : les données de santé sont sensibles. Si vous utilisez un tunnel ou un
> hébergement, préférez une solution chiffrée (HTTPS) et ne laissez pas l'app exposée
> publiquement sans protection.

## 🧪 Tests & outillage

- **Tests** (pytest, dans `tests/`) : chaque test utilise une base SQLite
  **temporaire et déterministe** — la vraie `data/infirmiere.db` n'est jamais modifiée.

  ```bash
  pip install pytest
  python -m pytest
  ```

- **Lint** (Ruff, configuration dans `pyproject.toml`) :

  ```bash
  pip install ruff
  python -m ruff check .
  ```

- **CI** (`.github/workflows/ci.yml`) : à chaque push/PR sur `main`, GitHub Actions
  installe les dépendances, lance Ruff puis pytest.

- **Logging** : `app.py` et `database.py` journalisent les événements critiques
  (sauvegardes, restauration, géocodage, erreurs) via le module standard `logging`.

## 🔒 Sécurité & mot de passe

- La première fois que l'app démarre, aucun mot de passe n'est défini : un avertissement
  apparaît dans la barre latérale avec un formulaire « **Définir un mot de passe** ».
- Une fois défini, chaque session (même navigateur) demande le mot de passe avant
  d'afficher l'application ; **« 🔓 Se déconnecter »** ferme la session.
- Le mot de passe est stocké **en local**, haché (**PBKDF2-SHA256, 600 000
  itérations** + sel, recommandation OWASP 2023) dans `data/password.json` —
  jamais en clair, jamais versionné. Les hachages existants (100 000 itérations)
  restent valides : le nombre d'itérations est conservé par enregistrement.
- **Verrouillage anti brute-force** : après **5 tentatives échouées**, la
  connexion est bloquée pendant **30 secondes** (l'écran de connexion indique
  l'attente restante). Le verrouillage est levé par une connexion réussie ou
  une redéfinition du mot de passe.
- Pour réinitialiser : supprimez `data/password.json` (ou demandez une réinitialisation
  locale — l'app n'expose pas de fonction « mot de passe oublié » par conception
  d'application locale).

> 💡 Le mot de passe protège l'interface, pas le fichier de base : conservez également
> les sauvegardes et `data/` en lieu sûr, et utilisez un tunnel HTTPS (voir plus haut)
> si vous accédez à l'app depuis le réseau.

## 🔐 RGPD & protection des données

L'application traite des **données de santé** (art. 9 RGPD — catégorie
*spéciale*). La responsable du traitement est **l'utilisatrice** (l'infirmière
à domicile), dans le cadre de son activité. Une page « **🔐 Confidentialité** »
dans l'application détaille ce qui suit.

**Données traitées** — identité (nom, prénom, naissance, sexe), coordonnées
(adresse, téléphone, email, mutuelle), **NISS**, données de santé (allergies,
médicaments, notes, interventions), coordonnées GPS (uniquement si géocodage
autorisé), date d'information/consentement du patient (art. 13-14).

**Sous-traitants** (transmission uniquement au moment de l'action) :

| Service | Quand | Données transmises |
|---|---|---|
| Nominatim (OpenStreetMap) | case d'autorisation cochée dans « Localisation » | l'adresse à géocoder |
| Google Maps | clic sur le lien « Itinéraire » | l'adresse (dans l'URL) |

**Aucune télémétrie** : les statistiques d'usage Streamlit sont désactivées
(`gatherUsageStats=false`). Le reste est 100 % local (fichier SQLite sur
l'appareil).

**Rétention** — les données sont conservées jusqu'à suppression de
`data/infirmiere.db` (suppression = droit à l'effacement) ; **5 sauvegardes**
maximum sont conservées automatiquement.

**Vos droits (art. 15-21)** — *accès/portabilité* : exports CSV (liste des
patients, facturation) ; *rectification* : formulaire « ✏️ Modifier le patient »
; *effacement* : « 🗑️ Supprimer ce patient » (confirmation explicite).

**Sécurité (art. 32)** — base SQLite locale, aucun serveur distant ; mot de
passe PBKDF2-SHA256 600 000 it. + sel ; verrouillage anti brute-force
(5 échecs → 30 s) ; le **fichier temporaire de restauration est supprimé**
après usage ; **journaux sans PII** (ni nom, ni adresse, ni téléphone — seul
l'identifiant interne est consigné) ; popups de la carte échappés contre le
XSS ; Docker non-root ; HTTPS recommandé pour tout accès distant.

**Données de démonstration opt-in** — la base démarre **vide** ; les
personnes fictives (avec données de santé) ne sont créées qu'explicitement :
`NURSE_SEED_DEMO=1 streamlit run app.py`.

> ⚠️ Si vous exposez l'app via un tunnel (`cloudflared`, `ngrok`) ou un
> hébergement : HTTPS + mot de passe sont indispensables, et les sauvegardes
> doivent rester en lieu sûr (elles contiennent des données de santé).

## 🐳 Docker

Image officielle fournie (`Dockerfile`) : utilisateur non-root, santé du service vérifiée
automatiquement, données isolées dans `/data`.

```bash
# Construire l'image
docker build -t nurse-planner .

# Lancer avec une base persistée (volume)
docker run -d --name nurse-planner -p 8501:8501 -v nurse_data:/data nurse-planner

# Ouvrir http://localhost:8501
```

Le dossier de données du conteneur est surchargeable via la variable
`NURSE_DATA_DIR` (défaut `/data`).

## 📝 Notes

- **Thème & design** : identité « carnet d'agenda papier » — papier crème pointé et
  grainé, rose poudré, titres manuscrits (Caveat) soulignés au feutre, spirale de
  reliure sur la tranche, scotch washi sur les formulaires et post-its, badges-stickers
  pastel, en-têtes de jour cerclés façon agenda (Aujourd'hui + vue Semaine) et icônes
  rose/blanches. Couleurs de base dans `.streamlit/config.toml` et `manifest.json`,
  finitions CSS (post-it de métriques, boutons pastille, cibles tactiles ≥ 48 px sur
  mobile) injectées par `app.py`.
- Les données sont stockées localement dans `data/infirmiere.db` (aucun serveur distant).
- **RGPD** : les données de santé sont sensibles. Pensez à sauvegarder régulièrement
  (barre latérale) et à ne partager le fichier de base qu'avec précaution.
- Pour repartir de zéro, supprimez simplement le fichier `data/infirmiere.db`.
