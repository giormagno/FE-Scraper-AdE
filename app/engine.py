import os
import re
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

class FEScraperEngine:
    def __init__(self, logger_func):
        self.logger = logger_func
        self.session = self._create_session()
        self.headers_cons = {}
        self.headers_token = {}

    def _create_session(self) -> requests.Session:
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Connection": "keep-alive",
        })
        return s

    def login(self, cf: str, pin: str, password: str) -> str:
        self.logger("Avvio login...")
        self.session.cookies.set_cookie(requests.cookies.create_cookie(domain="ivaservizi.agenziaentrate.gov.it", name="LFR_SESSION_STATE_20159", value=unix_ms()))
        self.session.cookies.set_cookie(requests.cookies.create_cookie(domain="ivaservizi.agenziaentrate.gov.it", name="LFR_SESSION_STATE_10811916", value=unix_ms()))

        r = self.session.get("https://ivaservizi.agenziaentrate.gov.it/portale/web/guest", verify=False)
        if r.status_code != 200:
            raise Exception("Impossibile connettersi alla homepage.")

        payload = {
            "_58_saveLastPath": "false",
            "_58_redirect": "",
            "_58_doActionAfterLogin": "false",
            "_58_login": cf,
            "_58_pin": pin,
            "_58_password": password,
        }
        r = self.session.post(
            "https://ivaservizi.agenziaentrate.gov.it/portale/home"
            "?p_p_id=58&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view"
            "&p_p_col_id=column-1&p_p_col_pos=3&p_p_col_count=4"
            "&_58_struts_action=%2Flogin%2Flogin",
            data=payload
        )

        m = re.findall(r"Liferay\.authToken = '.*';", r.text)
        if not m:
            with open("debug_login_error.html", "w", encoding="utf-8") as f:
                f.write(r.text)
            raise Exception("Liferay.authToken non trovato. Controlla debug_login_error.html")

        p_auth = m[0].replace("Liferay.authToken = '", "").replace("';", "")
        
        r = self.session.get(f"https://ivaservizi.agenziaentrate.gov.it/dp/api?v={unix_ms()}")
        if r.status_code != 200:
            raise Exception("Login fallito (dp/api error).")

        self.logger("Login effettuato con successo.")
        return p_auth

    def select_engine(self, engine_type: str, p_auth: str, piva: str, sdi_role: str) -> str:
        """
        Motore di selezione incarico.
        engine_type: "DELEGA_DIRETTA", "ME_STESSO", "INTERMEDIARIO"
        sdi_role: "FOL" o "ENT"
        RITORNA: La PIVA operativa (rilevata o confermata).
        """
        if engine_type == "DELEGA_DIRETTA":
            self._select_delega_diretta(p_auth, piva)
            return piva
        elif engine_type == "ME_STESSO":
            # Uso il nuovo motore specializzato che rileva la PIVA
            engine = MeStessoEngine(self.session, self.logger)
            return engine.run_selection(p_auth)
        elif engine_type == "INTERMEDIARIO":
            # Uso il nuovo motore specializzato
            engine = IntermediarioEngine(self.session, self.logger)
            engine.run_selection(p_auth, piva, sdi_role)
            return piva
        else:
            raise ValueError(f"Motore sconosciuto: {engine_type}")

    def _select_delega_diretta(self, p_auth: str, piva: str):
        self.logger(f"Selezione Delega Diretta per {piva}")
        
        # Step 1: scelta "Delega Diretta"
        payload = {"sceltaincarico": "ut1a3", "tipoincaricante": "incIncaricato"}
        url1 = (
            "https://ivaservizi.agenziaentrate.gov.it/portale/scelta-utenza-lavoro"
            f"?p_auth={p_auth}"
            "&p_p_id=SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet"
            "&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1"
            "&_SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet_javax.portlet.action=tipoUtenzaAction"
        )
        r1 = self.session.post(url1, data=payload)
        self.logger(f"  Step 1 (tipoUtenzaAction): {r1.status_code}")

        # Step 2: invio PIVA
        payload = {"cf_inserito": piva}
        url2 = (
            "https://ivaservizi.agenziaentrate.gov.it/portale/scelta-utenza-lavoro"
            f"?p_auth={p_auth}"
            "&p_p_id=SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet"
            "&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1"
            "&_SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet_javax.portlet.action=delegaDirettaAction"
        )
        r2 = self.session.post(url2, data=payload)
        self.logger(f"  Step 2 (delegaDirettaAction): {r2.status_code}")

        # Step 3: accettazione disclaimer (GET)
        url3 = (
            "https://ivaservizi.agenziaentrate.gov.it/portale/scelta-utenza-lavoro"
            f"?p_auth={p_auth}"
            "&p_p_id=SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet"
            "&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1"
            "&_SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet_javax.portlet.action=proseguiDelegaAction"
        )
        r3 = self.session.get(url3)
        self.logger(f"  Step 3 (proseguiDelegaAction): {r3.status_code}")

        if r3.status_code != 200:
             raise Exception(f"Errore selezione Delega Diretta (Status {r3.status_code}).")

    def get_b2b_tokens(self):
        self.logger("Richiesta Token B2B...")
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
