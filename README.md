# Backend FastAPI — Pixel (Starter)

Ce petit starter te permet de démarrer l'API pour la version mobile.

## Prérequis
- Python 3.10+
- `pip`, `venv`
- Un projet Supabase existant avec les tables déjà créées (Users, Parcours, Suivi_Parcours, Entrainement, Observations).

## Configuration
Copie `.env.example` vers `.env` et remplis :
```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```
> Utilise la **service role key** uniquement côté serveur.

## Lancer en local
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Endpoints
- `GET /health` — ping
- `GET /parcours/position?type=Addition|Soustraction|Multiplication&user_id=1` — position de départ (MVP: premier niveau du type)

Prochaines étapes :
- Ajouter la vérification du **JWT Supabase** (middleware) et lire `user_id` depuis le token au lieu du paramètre.
- Implémenter la vraie logique "dernière position" selon Suivi_Parcours, comme dans ton app Streamlit.
- Ajouter `POST /exercices/generer`, `POST /entrainement`, `POST /observations`, `POST /progression/analyser`.
