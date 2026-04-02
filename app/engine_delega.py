from typing import Any, Callable, Dict
import requests


class DelegaDirettaEngine:
    """
    Motore specifico per la selezione dell'utenza "Delega Diretta".
    Mantiene la stessa sequenza di chiamate storicamente usata dal motore principale.
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

    def run_selection(self, p_auth: str, piva: str) -> str:
        """
        Esegue la selezione dell'utenza delegata e conferma il soggetto su cui operare.
        """
        _ = p_auth
        payload = {
            "tipoutenza": "delegaDiretta",
            "tipoDelega": "delDiretta",
            "cf": piva,
            "pIva": piva,
        }
        data = self._wizard_select(payload)
        confirmed_piva = self._extract_piva_value(data, piva.strip())
        if not confirmed_piva:
            raise Exception("PIVA non confermata dal wizard per utenza 'DELEGA_DIRETTA'.")
        self.logger(f"PIVA confermata dal wizard: {confirmed_piva}")
        return confirmed_piva
