# app/services/evolution.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from datetime import date

OP_TYPES = ("addition", "soustraction", "multiplication")
# Mapping interne entre la valeur normalisée et la valeur stockée en DB (majuscule initiale)
OP_TO_DB = {
    "addition": "Addition",
    "soustraction": "Soustraction",
    "multiplication": "Multiplication",
}

EVOL_PROGRESSION = "progression"
EVOL_STAGNATION  = "stagnation"
EVOL_REGRESSION  = "régression"


class EvolutionService:
    """
    Fenêtre = toutes les obs > Derniere_Observation_Id (par utilisateur + opération).
    Seuils: >0.95 progression, <0.5 régression, sinon stagnation.
    Voisins par (Type_Operation, Niveau). Auto-init niveau 1 si aucun suivi.
    """

    def __init__(self, sb_client):
        self.sb = sb_client

    # --- helper compat multi-SDK pour les SELECT ---
    def _q(self, table: str, columns: str = "*"):
        # tente from_(...).select(...)
        b = self.sb.from_(table)
        sel = getattr(b, "select", None)
        if callable(sel):
            return sel(columns)
        # tente table(...).select(...)
        b2 = self.sb.table(table)
        sel2 = getattr(b2, "select", None)
        if callable(sel2):
            return sel2(columns)
        # dernier recours: builder sans select (récupérera tout)
        return b


    # --------------------- helpers ---------------------
    @staticmethod
    def _norm_op(op: str) -> str:
        return (op or "").strip().lower()

    def _op_db(self, op: str) -> str:
        opn = self._norm_op(op)
        if opn not in OP_TYPES:
            raise ValueError(f"Operation inconnue: {op}")
        return OP_TO_DB[opn]



    # --------------------- lectures & écritures DB ---------------------
    def _last_suivi_for_op(self, user_id: int, op_type: str) -> Optional[Dict]:
        """
        Récupère la DERNIÈRE ligne de Suivi_Parcours (append-only) pour ce user ET ce type d'opération.
        Implémentation en 2 temps:
          1) on prend les 50 derniers suivis de l'utilisateur
          2) pour chacun on charge le Parcours et on compare Type_Operation
        """
        suivis = (
            self._q("Suivi_Parcours", "id, Parcours_Id, Derniere_Observation_Id")
            .eq("Users_Id", user_id)
            .order("id", desc=True)
            .limit(50)
            .execute()
            .data
            or []
        )
        wanted = self._op_db(op_type)
        for s in suivis:
            p = (
                self._q("Parcours", "id, Niveau, Critere, Type_Operation")
                .eq("id", s["Parcours_Id"])
                .limit(1)
                .execute()
                .data
            )
            if p and p[0].get("Type_Operation") == wanted:
                return {"suivi": s, "parcours": p[0]}
        return None

    def _initial_parcours_for_op(self, op_type: str) -> Dict:
        wanted = self._op_db(op_type)
        rows = (
            self._q("Parcours", "id, Niveau, Critere, Type_Operation")
            .eq("Type_Operation", wanted)
            .order("Niveau")
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            rows = (
                self._q("Parcours", "id, Niveau, Critere, Type_Operation")
                .eq("Type_Operation", wanted)
                .order("id")
                .limit(1)
                .execute()
                .data
            )
        if not rows:
            raise ValueError(f"Aucun Parcours pour Type_Operation={wanted}")
        return rows[0]

    def _ensure_initialized(self, user_id: int, op_type: str) -> Dict:
        last = self._last_suivi_for_op(user_id, op_type)
        if last:
            return last
        p0 = self._initial_parcours_for_op(op_type)
        res_ins = (
            self.sb.table("Suivi_Parcours")
            .insert({
                "Users_Id": user_id,
                "Parcours_Id": p0["id"],
                "Date": date.today().isoformat(),
                "Type_Evolution": "initialisation",
                "Taux_Reussite": 0.0,
                "Derniere_Observation_Id": None,
            })
            .execute()
        )
        ins = (res_ins.data[0] if getattr(res_ins, "data", None) else {"Parcours_Id": p0["id"], "Derniere_Observation_Id": None})
        return {"suivi": ins, "parcours": p0}


    def _neighbors_by_niveau(self, op_type: str, current_niveau: int) -> Tuple[Optional[Dict], Dict, Optional[Dict]]:
        wanted = self._op_db(op_type)
        cur_rows = (
            self._q("Parcours", "id, Niveau, Critere, Type_Operation")
            .eq("Type_Operation", wanted)
            .eq("Niveau", current_niveau)
            .limit(1)
            .execute()
            .data or []
        )
        cur = cur_rows[0] if cur_rows else None

        prev = (
            self._q("Parcours", "id, Niveau, Critere, Type_Operation")
            .eq("Type_Operation", wanted)
            .lt("Niveau", current_niveau)
            .order("Niveau", desc=True)
            .limit(1)
            .execute()
            .data
        )
        nxt = (
            self._q("Parcours", "id, Niveau, Critere, Type_Operation")
            .eq("Type_Operation", wanted)
            .gt("Niveau", current_niveau)
            .order("Niveau")
            .limit(1)
            .execute()
            .data
        )
        return (prev[0] if prev else None, cur, nxt[0] if nxt else None)

    def _user_entrainement_ids(self, user_id: int) -> List[int]:
        rows = (
            self._q("Entrainement", "id")
            .eq("Users_Id", user_id)
            .execute()
            .data
            or []
        )
        return [int(r["id"]) for r in rows]

    def _window_stats_since(self, user_id: int, op_type: str, last_obs_id: Optional[int]) -> Dict:
        """
        Fenêtre: toutes les Observations de CE user pour cette opération, id > last_obs_id.
        """
        entr_ids = self._user_entrainement_ids(user_id)
        if not entr_ids:
            return {"total": 0, "corrects": 0, "last_id_included": last_obs_id or 0}

        wanted = self._op_db(op_type)
        q = (
            self._q("Observations", "id, Etat")
            .in_("Entrainement_Id", entr_ids)
            .eq("Operation", wanted)
        )
        if last_obs_id:
            q = q.gt("id", int(last_obs_id))
        rows = q.order("id").execute().data or []

        total = len(rows)
        corrects = sum(1 for r in rows if r.get("Etat") == "VRAI")
        last_id = (rows[-1]["id"] if rows else (last_obs_id or 0))
        return {"total": total, "corrects": corrects, "last_id_included": last_id}

    @staticmethod
    def _decide(pct: float, has_prev: bool, has_next: bool) -> str:
        if pct > 0.95 and has_next:
            return EVOL_PROGRESSION
        if pct < 0.5 and has_prev:
            return EVOL_REGRESSION
        return EVOL_STAGNATION

    # --------------------- API publique ---------------------
    def evaluate_and_record_if_needed(self, user_id: int, op_type: str) -> Optional[Dict]:
        op_type = self._norm_op(op_type)
        if op_type not in OP_TYPES:
            return None

        ctx = self._ensure_initialized(user_id, op_type)
        last_suivi = ctx["suivi"]
        cur_parcours = ctx["parcours"]
        critere = int(cur_parcours.get("Critere") or 0)

        stats = self._window_stats_since(
            user_id=user_id,
            op_type=op_type,
            last_obs_id=last_suivi.get("Derniere_Observation_Id"),
        )
        if stats["total"] < critere or critere <= 0:
            return None

        pct = (stats["corrects"] / stats["total"]) if stats["total"] else 0.0
        prev_p, cur_p, next_p = self._neighbors_by_niveau(op_type, int(cur_parcours["Niveau"]))
        decision = self._decide(pct, has_prev=prev_p is not None, has_next=next_p is not None)

        arrival = cur_p
        if decision == EVOL_PROGRESSION and next_p:
            arrival = next_p
        elif decision == EVOL_REGRESSION and prev_p:
            arrival = prev_p

        res_ins = (
            self.sb.table("Suivi_Parcours")
            .insert({
                "Users_Id": user_id,
                "Parcours_Id": arrival["id"],
                "Date": date.today().isoformat(),
                "Type_Evolution": decision,
                "Taux_Reussite": round(pct, 4),
                "Derniere_Observation_Id": int(stats["last_id_included"]),
            })
            .execute()
        )
        ins = res_ins.data[0] if getattr(res_ins, "data", None) else None


        return {
            "suivi": ins,
            "operation": op_type,
            "from": {"parcours_id": cur_parcours["id"], "niveau": cur_parcours["Niveau"]},
            "to":   {"parcours_id": arrival["id"], "niveau": arrival["Niveau"]},
            "type": decision,
            "taux_reussite": round(pct, 4),
            "window": stats,
        }

    def positions_for_user(self, user_id: int) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        for op in OP_TYPES:
            last = self._last_suivi_for_op(user_id, op)
            if last:
                p = last["parcours"]
            else:
                p = self._initial_parcours_for_op(op)
            out[op] = {"parcours_id": p["id"], "niveau": p["Niveau"], "critere": p["Critere"]}
        return out
