import json
from typing import Any, Callable, Dict, List, Optional
import requests

class IntermediarioEngine:
    """
    Motore logico per il caso "intermediario", che nel wizard AdE corrente
    corrisponde alla voce "Incaricato" con selezione dell'azienda dal dropdown.
    """
    def __init__(
        self,
        session: requests.Session,
        logger_func,
        wizard_proceed_func: Callable[[Dict[str, Any]], Dict[str, Any]],
        wizard_set_user_choice_func: Callable[[Dict[str, Any]], Dict[str, Any]],
        extract_piva_func: Callable[[Dict[str, Any], str], str],
        wizard_template_func: Callable[[bool], Dict[str, Any]],
    ):
        self.session = session
        self.logger = logger_func
        self._wizard_proceed = wizard_proceed_func
        self._wizard_set_user_choice = wizard_set_user_choice_func
        self._extract_piva_value = extract_piva_func
        self._get_wizard_template = wizard_template_func

    def _normalize(self, value: Any) -> str:
        return str(value or "").strip().upper()

    def _build_position_label(self, incarico: Dict[str, Any]) -> str:
        incaricante = incarico.get("incaricante")
        if not isinstance(incaricante, dict):
            return ""

        cf = str(incaricante.get("cf", "")).strip()
        sede = str(incaricante.get("sede", "")).strip()
        if not cf:
            return ""
        if not sede or sede.upper() == "FOL":
            return cf
        return f"{cf}-{sede}"

    def _extract_incarichi(self, template: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        roots: List[Optional[Dict[str, Any]]] = [template]
        nested = template.get("template")
        if isinstance(nested, dict):
            roots.append(nested)

        for root in roots:
            if not isinstance(root, dict):
                continue
            richiesta = root.get("richiestaIncarichi")
            if not isinstance(richiesta, dict):
                continue
            incarichi = richiesta.get("incarichi")
            if isinstance(incarichi, list):
                candidates.extend(item for item in incarichi if isinstance(item, dict))

        return candidates

    def _find_matching_incarico(self, incarichi: List[Dict[str, Any]], target: str) -> Optional[Dict[str, Any]]:
        target_norm = self._normalize(target)
        exact_label: Optional[Dict[str, Any]] = None
        exact_cf: Optional[Dict[str, Any]] = None
        suffixed_cf: Optional[Dict[str, Any]] = None

        for incarico in incarichi:
            label = self._normalize(self._build_position_label(incarico))
            incaricante = incarico.get("incaricante") if isinstance(incarico.get("incaricante"), dict) else {}
            cf = self._normalize(incaricante.get("cf", ""))

            if label == target_norm:
                exact_label = incarico
                break

            if cf == target_norm and "-" not in label and exact_cf is None:
                exact_cf = incarico

            if (cf == target_norm or label.startswith(f"{target_norm}-")) and "-" in label and suffixed_cf is None:
                suffixed_cf = incarico

        return exact_label or exact_cf or suffixed_cf

    def _derive_role_from_position(self, position_label: str, fallback: str) -> str:
        return "ENT" if "-" in position_label else (fallback or "FOL")

    def _extract_piva_candidates(self, template: Dict[str, Any]) -> List[str]:
        values: List[str] = []
        roots: List[Optional[Dict[str, Any]]] = [template]
        nested = template.get("template")
        if isinstance(nested, dict):
            roots.append(nested)

        for root in roots:
            if not isinstance(root, dict):
                continue
            piva_values = root.get("PIva")
            if piva_values is None:
                piva_values = root.get("pIva")

            if isinstance(piva_values, list):
                for item in piva_values:
                    if isinstance(item, dict):
                        candidate = str(item.get("piva", "")).strip()
                    else:
                        candidate = str(item or "").strip()
                    if candidate and candidate not in values:
                        values.append(candidate)
            elif isinstance(piva_values, dict):
                candidate = str(piva_values.get("piva", "")).strip()
                if candidate and candidate not in values:
                    values.append(candidate)
            elif isinstance(piva_values, str):
                candidate = piva_values.strip()
                if candidate and candidate not in values:
                    values.append(candidate)

        return values

    def _choose_piva(self, candidates: List[str], target: str, fallback: str) -> str:
        target_norm = self._normalize(target)
        for candidate in candidates:
            if self._normalize(candidate) == target_norm:
                return candidate
        if len(candidates) == 1:
            return candidates[0]
        if fallback:
            return fallback
        return target

    def run_selection(self, p_auth: str, piva: str, sdi_role: str) -> str:
        """
        Esegue il flusso reale osservato sul portale:
        1. scelta wizard "Incaricato"
        2. selezione dal dropdown "incaricante"
        3. selezione automatica della PIVA, se unica
        4. conferma finale con setUserChoice
        """
        self.logger(f"Inizio procedura Incaricato per cliente {piva}")
        self.logger("Il wizard corrente usa la voce: INCARICATO")
        _ = p_auth
        wizard_tipoutenza = "incaricato"
        step1_data = self._wizard_proceed({"tipoutenza": wizard_tipoutenza, "cf": ""})
        template = step1_data if isinstance(step1_data, dict) else self._get_wizard_template(refresh=True)
        incarichi = self._extract_incarichi(template)
        if not incarichi:
            raise Exception("Nessuna posizione disponibile restituita dal wizard per l'utenza 'INTERMEDIARIO'.")

        selected = self._find_matching_incarico(incarichi, piva.strip())
        if selected is None:
            available = [label for label in (self._build_position_label(item) for item in incarichi) if label]
            preview = ", ".join(available[:10]) if available else "nessuna"
            raise Exception(
                "La PIVA richiesta non compare tra le posizioni disponibili del wizard. "
                f"PIVA richiesta: {piva}. Posizioni trovate: {preview}"
            )

        position_label = self._build_position_label(selected)
        detected_role = self._derive_role_from_position(position_label, sdi_role)
        self.logger(f"Posizione selezionata dal wizard: {position_label} ({detected_role})")

        step2_payload = {
            "tipoutenza": wizard_tipoutenza,
            "incaricante": json.dumps(selected, ensure_ascii=False),
            "tipoincaricante": "incaricoDiretto",
            "pIva": None,
        }
        step2_data = self._wizard_proceed(step2_payload)

        fallback_piva = str(selected.get("incaricante", {}).get("cf", "")).strip() or piva.strip()
        piva_candidates = self._extract_piva_candidates(step2_data if isinstance(step2_data, dict) else {})
        selected_piva = self._choose_piva(piva_candidates, piva.strip(), fallback_piva)
        if piva_candidates:
            self.logger(f"PIVA candidata selezionata dal wizard: {selected_piva}")

        final_payload = {
            "tipoutenza": wizard_tipoutenza,
            "incaricante": step2_payload["incaricante"],
            "tipoincaricante": "incaricoDiretto",
            "cf": fallback_piva,
        }
        if piva_candidates:
            final_payload["pIva"] = selected_piva

        data = self._wizard_set_user_choice(final_payload)
        confirmed_piva = self._extract_piva_value(data, selected_piva)
        if not confirmed_piva:
            raise Exception("PIVA non confermata dal wizard per utenza 'INTERMEDIARIO'.")
        self.logger(f"PIVA confermata dal wizard: {confirmed_piva}")
        self.logger("Procedura Incaricato completata con successo.")
        return confirmed_piva
