from typing import Any, Callable, Dict
import requests

class MeStessoEngine:
    """
    Motore specifico per l'accesso come "Me stesso".
    In questo caso la PIVA non viene inserita manualmente ma rilevata dal portale.
    """
    def __init__(
        self,
        session: requests.Session,
        logger_func,
        wizard_select_func: Callable[[Dict[str, str]], Dict[str, Any]],
        extract_piva_func: Callable[[Dict[str, Any], str], str],
    ):
        self.session = session
        self.logger = logger_func
        self._wizard_select = wizard_select_func
        self._extract_piva_value = extract_piva_func

    def run_selection(self, p_auth: str) -> str:
        """
        Esegue la selezione del ruolo Me Stesso e restituisce la PIVA rilevata dal portale.
        """
        self.logger("Inizio procedura 'Me stesso'...")
        _ = p_auth
        payload = {
            "tipoutenza": "meStesso",
            "cf": "",
        }
        data = self._wizard_select(payload)
        detected_piva = self._extract_piva_value(data, "")
        if not detected_piva:
            raise Exception("PIVA non rilevata per utenza 'ME_STESSO'.")
        self.logger(f"  PIVA rilevata dal portale: {detected_piva}")
        return detected_piva
