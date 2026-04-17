# NutriTrack

NutriTrack est une plateforme de suivi de chaîne du froid composée de deux parties:

- un backend Python/FastAPI qui simule le flux multi-agents et expose les données métier;
- un dashboard React/Vite qui affiche les indicateurs, les anomalies et les recommandations.

## Structure

- `NutriTrack_Source_Code/` : logique métier, agents, API et génération des données du dashboard
- `NutriTrack_Dashboard_App/` : interface web du tableau de bord

## Prérequis

- Python 3.10 ou plus
- Node.js 18 ou plus
- une clé API Groq si vous voulez activer l’assistant LLM

## Installation du backend

```powershell
cd NutriTrack_Source_Code
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Créez ensuite un fichier `.env` si nécessaire, par exemple:

```env
GROQ_API_KEY=your_key_here
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_ENFORCE_AUTH=true
```

Lancement de l’API:

```powershell
uvicorn nutritrack.api.main:app --reload
```

## Installation du dashboard

```powershell
cd NutriTrack_Dashboard_App
npm install
npm run dev
```

Le dashboard Vite est configuré pour proxyfier `/api` vers `http://127.0.0.1:8000`.

Au démarrage, le frontend affiche maintenant un écran Login/Signup.
Il appelle `/api/auth/login` ou `/api/auth/signup`, stocke le JWT (`access_token`) en local, puis envoie automatiquement `Authorization: Bearer <token>` sur les appels API protégés.

## Points d’entrée utiles

- `GET /api/health` : état du backend
- `POST /api/auth/signup` : création d’un compte utilisateur (Supabase Auth)
- `POST /api/auth/login` : récupération du JWT (`access_token`)
- `GET /api/auth/me` : profil courant à partir du JWT envoyé en Bearer
- `GET /api/dashboard` : données agrégées pour l’interface
- `POST /api/shipment-requests` : (client/admin) création d’une demande d’expédition (quantité, origine, destination)
- `GET /api/shipment-requests` : liste des demandes (admin: toutes, client: ses propres demandes)
- `POST /api/shipment-requests/{id}/confirm` : (admin) confirme la demande et déclenche le Transport Agent IA
- `POST /api/shipment-requests/{id}/stage` : (admin) fait avancer le cycle de vie (`storage` -> `delivery` -> `destination`)
- `POST /api/reason` : exécution d’un raisonnement sur des données fournies
- `POST /api/assistant` : réponse assistée par Groq si la clé est configurée

Les routes métier (`/api/dashboard`, `/api/analyze`, `/api/reason`, `/api/assistant`) sont protégées par JWT si `SUPABASE_ENFORCE_AUTH=true`.

Le workflow de demandes d’expédition est aussi protégé par JWT. Le rôle `client` peut créer/consulter ses demandes, et le rôle `admin` peut confirmer une demande pour lancer le Transport Agent:

- Optimisation d’itinéraire via OSRM (OpenStreetMap)
- Analyse météo via Open-Meteo
- Calcul du risque chaleur sur trajet
- Suggestions de reroutage en temps réel

Exemple d’appel authentifié:

```bash
curl -H "Authorization: Bearer <access_token>" http://127.0.0.1:8000/api/dashboard
```

## Génération des données

Le backend écrit automatiquement le fichier de dashboard généré dans `NutriTrack_Source_Code/nutritrack/data/dashboard_data.json`.
Ce fichier est ignoré par Git car il est reconstruit à chaque exécution.

## Notes

- Si vous publiez ce projet sur GitHub, poussez les deux dossiers de travail depuis la racine `Linka`.
- Le flux principal passe par l’API FastAPI, puis le dashboard lit les données via le proxy Vite.
- Un exemple de configuration est fourni dans `NutriTrack_Source_Code/.env.example`.
- La licence du projet est `LICENSE` à la racine.