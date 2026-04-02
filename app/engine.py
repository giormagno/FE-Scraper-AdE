import pytz
import requests
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from requests.packages.urllib3.exceptions import InsecureRequestWarning

def unix_ms() -> str:
    dt = datetime.now(tz=pytz.utc)
    return str(int(dt.timestamp() * 1000))

def add_months(sourcedate: datetime, months: int) -> datetime:
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(
        sourcedate.day,
        [31, 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28, 
         31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
    )
    return datetime(year, month, day)

def get_date_chunks(start_str: str, end_str: str) -> List[Tuple[str, str]]:
    start_date = datetime.strptime(start_str, "%d/%m/%Y")
    final_end = datetime.strptime(end_str, "%d/%m/%Y")
    chunks: List[Tuple[str, str]] = []
    current_start = start_date
    while current_start < final_end:
        current_end = add_months(current_start, 3)
        if current_end > final_end:
            current_end = final_end
        chunks.append((current_start.strftime("%d/%m/%Y"), current_end.strftime("%d/%m/%Y")))
        if current_end == final_end:
            break
        current_start = current_end
    return chunks

from app.engine_intermediario import IntermediarioEngine
from app.engine_mestesso import MeStessoEngine
from app.engine_delega import DelegaDirettaEngine

class FEScraperEngine:
    def __init__(self, logger_func):
        self.logger = logger_func
        self.session = self._create_session()
        self.headers_cons = {}
        self.headers_token = {}
        self._x_appl: Optional[str] = None

    def _create_session(self) -> requests.Session:
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Connection": "keep-alive",
        })
        return s

    def _safe_json(self, r: requests.Response) -> Dict[str, Any]:
        try:
            data = r.json()
            if isinstance(data, dict):
                return data
            return {"_raw": data}
        except Exception:
            return {"_raw_text": r.text}

    def _request_with_x_appl(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        if self._x_appl and "x-appl" not in headers:
            headers["x-appl"] = self._x_appl

        r = self.session.request(method, url, headers=headers, **kwargs)
        if r.status_code == 409 and r.headers.get("x-appl"):
            self._x_appl = r.headers["x-appl"]
            headers["x-appl"] = self._x_appl
            r = self.session.request(method, url, headers=headers, **kwargs)

        return r

    def _init_new_portale_session(self) -> None:
        init_url = "https://portale.agenziaentrate.gov.it/portale-rest/rs/initPortale?to=FATBTB"
        r = self.session.get(init_url, allow_redirects=False, verify=False)

        if r.status_code == 501 and r.headers.get("x-red"):
            r = self.session.get(r.headers["x-red"], allow_redirects=False, verify=False)

        if r.status_code not in (200, 204):
            raise Exception(f"Init Portale fallita (status {r.status_code}).")

        perm_url = "https://portale.agenziaentrate.gov.it/portale-rest/rs/servizi/permessiFatturazione"
        r = self._request_with_x_appl("GET", perm_url, verify=False)
        if r.status_code != 200:
            raise Exception(f"Permessi fatturazione non ottenuti (status {r.status_code}).")

        vai_url = "https://portale.agenziaentrate.gov.it/portale-rest/rs/servizi/vaiAFatturazione/b2b"
        r = self._request_with_x_appl("GET", vai_url, verify=False)
        if r.status_code != 200:
            raise Exception(f"Accesso a fatturazione non riuscito (status {r.status_code}).")

        target = self._safe_json(r).get("url")
        if not target:
            raise Exception("URL di instradamento a Fatturazione non presente nella risposta.")

        r = self.session.get(target, allow_redirects=True, verify=False)
        if r.status_code != 200:
            raise Exception(f"Redirect a Fatturazione fallito (status {r.status_code}).")

        init_light = "https://ivaservizi.agenziaentrate.gov.it/instr/instradamento-fatture-rest/rs/initLight"
        r = self._request_with_x_appl("GET", init_light, verify=False)
        if r.status_code != 200:
            raise Exception(f"Init wizard fallita (status {r.status_code}).")

        wizard_template = "https://ivaservizi.agenziaentrate.gov.it/instr/instradamento-fatture-rest/rs/wizardTemplate"
        r = self._request_with_x_appl("GET", wizard_template, verify=False)
        if r.status_code != 200:
            raise Exception(f"Wizard template non disponibile (status {r.status_code}).")

    def login(self, cf: str, pin: str, password: str) -> str:
        self.logger("Avvio login (nuovo flusso IAMPE)...")

        login_page = (
            "https://iampe.agenziaentrate.gov.it/sam/UI/Login"
            "?realm=%2Fagenziaentrate&service=auth&goto="
            "https%3A%2F%2Fportale.agenziaentrate.gov.it%2FPortaleWeb%2Fhome%3Fto%3DFATBTB"
        )
        r = self.session.get(login_page, verify=False)
        if r.status_code != 200:
            raise Exception(f"Pagina login IAMPE non raggiungibile (status {r.status_code}).")

        payload = {
            "username": cf,
            "password": password,
            "pin": pin,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/plain, */*"}
        r = self.session.post(
            "https://iampe.agenziaentrate.gov.it/api/login/telematico",
            json=payload,
            headers=headers,
            verify=False,
        )
        if r.status_code != 200:
            with open("debug_login_error.html", "w", encoding="utf-8") as f:
                f.write(f"Status Code: {r.status_code}\n\n{r.text}")
            raise Exception(f"Login IAMPE fallito (status {r.status_code}).")

        data = self._safe_json(r)
        esito = str(data.get("esito", "OK")).upper()
        if esito not in ("OK", "SUCCESS"):
            with open("debug_login_error.html", "w", encoding="utf-8") as f:
                f.write(str(data))
            raise Exception(f"Login IAMPE rifiutato: {data}")

        self._init_new_portale_session()
        self.logger("Login effettuato con successo.")
        return "NEW_LOGIN_FLOW"

    def _wizard_select(self, payload: Dict[str, str]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/plain, */*"}

        procedi_url = "https://ivaservizi.agenziaentrate.gov.it/instr/instradamento-fatture-rest/rs/procediWizard"
        r = self._request_with_x_appl("POST", procedi_url, json=payload, headers=headers, verify=False)
        if r.status_code != 200:
            raise Exception(f"Errore procediWizard (status {r.status_code}).")

        scelta_url = "https://ivaservizi.agenziaentrate.gov.it/instr/instradamento-fatture-rest/rs/setUserChoice"
        r = self._request_with_x_appl("POST", scelta_url, json=payload, headers=headers, verify=False)
        if r.status_code != 200:
            raise Exception(f"Errore setUserChoice (status {r.status_code}).")

        return self._safe_json(r)

    def _extract_piva_value(self, data: Dict[str, Any], fallback: str = "") -> str:
        value = data.get("pIva")
        if value is None:
            value = data.get("PIva")

        if isinstance(value, str):
            return value.strip() or fallback

        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                candidate = str(first.get("piva", "")).strip()
                if candidate:
                    return candidate

        if isinstance(value, dict):
            candidate = str(value.get("piva", "")).strip()
            if candidate:
                return candidate

        return fallback

    def select_engine(self, engine_type: str, p_auth: str, piva: str, sdi_role: str) -> str:
        """
        Motore di selezione incarico.
        engine_type: "DELEGA_DIRETTA", "ME_STESSO", "INTERMEDIARIO"
        sdi_role: "FOL" o "ENT"
        RITORNA: La PIVA operativa (rilevata o confermata).
        """
        self.logger(f"Selezione utenza con nuovo wizard: {engine_type}")
        if engine_type == "DELEGA_DIRETTA":
            engine = DelegaDirettaEngine(self.session, self.logger, self._wizard_select, self._extract_piva_value)
            return engine.run_selection(p_auth, piva)
        elif engine_type == "ME_STESSO":
            engine = MeStessoEngine(self.session, self.logger, self._wizard_select, self._extract_piva_value)
            return engine.run_selection(p_auth)
        elif engine_type == "INTERMEDIARIO":
            engine = IntermediarioEngine(self.session, self.logger, self._wizard_select, self._extract_piva_value)
            return engine.run_selection(p_auth, piva, sdi_role)
        else:
            raise ValueError(f"Motore sconosciuto: {engine_type}")

    def get_b2b_tokens(self):
        self.logger("Richiesta Token B2B...")
        preflight = self.session.get(
            "https://ivaservizi.agenziaentrate.gov.it/dp/PI2FC",
            verify=False,
        )
        self.logger(f"Preflight /dp/PI2FC: {preflight.status_code}")

        self.session.get(f"https://ivaservizi.agenziaentrate.gov.it/cons/cons-web/?v={unix_ms()}")
        headers = {"Accept": "application/json, text/plain, */*"}
        r = self.session.get(
            f"https://ivaservizi.agenziaentrate.gov.it/cons/cons-services/sc/tokenB2BCookie/get?v={unix_ms()}",
            headers=headers
        )
        if r.status_code != 200:
            raise Exception("Impossibile ottenere Token B2B.")

        self.headers_token = {
            "Accept": "application/json, text/plain, */*",
            "x-b2bcookie": r.headers.get("x-b2bcookie", ""),
            "x-token": r.headers.get("x-token", "")
        }
        
        self.headers_cons = {
            "Host": "ivaservizi.agenziaentrate.gov.it",
            "referer": f"https://ivaservizi.agenziaentrate.gov.it/cons/cons-web/?v={unix_ms()}",
            "accept": "application/json, text/plain, */*",
            "x-b2bcookie": self.headers_token["x-b2bcookie"],
            "x-token": self.headers_token["x-token"],
            "User-Agent": self.session.headers["User-Agent"]
        }
        self.logger("Token B2B ottenuti.")

    def fetch_invoices(self, start_str: str, end_str: str, category: str) -> Dict[str, Any]:
        chunks = get_date_chunks(start_str, end_str)
        all_invoices = []
        seen_uids = set()

        self.logger(f"Ricerca {category}...")

        for d_dal, d_al in chunks:
            dal_c = d_dal.replace("/", "")
            al_c = d_al.replace("/", "")
            
            if category == "RICEVUTE":
                url = f"https://ivaservizi.agenziaentrate.gov.it/cons/cons-services/rs/fe/ricevute/dal/{dal_c}/al/{al_c}/ricerca/ricezione?v={unix_ms()}"
            else:
                url = f"https://ivaservizi.agenziaentrate.gov.it/cons/cons-services/rs/fe/emesse/dal/{dal_c}/al/{al_c}?v={unix_ms()}"

            r = self.session.get(url, headers=self.headers_cons)
            
            # Fallback EMESSE
            if category == "EMESSE" and r.status_code == 404:
                url = f"https://ivaservizi.agenziaentrate.gov.it/cons/cons-services/rs/fe/emesse/dal/{dal_c}/al/{al_c}/ricerca/invio?v={unix_ms()}"
                r = self.session.get(url, headers=self.headers_cons)

            if r.status_code == 200:
                data = r.json()
                for inv in data.get("fatture", []):
                    uid = f"{inv.get('idFattura')}_{inv.get('tipoInvio')}"
                    if uid not in seen_uids:
                        seen_uids.add(uid)
                        all_invoices.append(inv)
        
        return {
            "totaleFatture": len(all_invoices),
            "fatture": all_invoices
        }
