import re
import requests
from app.engine import unix_ms

class MeStessoEngine:
    """
    Motore specifico per l'accesso come "Me stesso".
    In questo caso la PIVA non viene inserita manualmente ma rilevata dal portale.
    """
    def __init__(self, session: requests.Session, logger_func):
        self.session = session
        self.logger = logger_func

    def run_selection(self, p_auth: str) -> str:
        """
        Esegue la selezione del ruolo Me Stesso e restituisce la PIVA rilevata dal portale.
        """
        self.logger("Inizio procedura 'Me stesso'...")
        
        # Step 1: Selezione ruolo "Me stesso"
        url_base = (
            "https://ivaservizi.agenziaentrate.gov.it/portale/scelta-utenza-lavoro"
            f"?p_auth={p_auth}"
            "&p_p_id=SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet"
            "&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1"
        )
        url_step1 = f"{url_base}&_SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet_javax.portlet.action=meStessoAction"
        payload1 = {"tipoutenza": "Me stesso"}
        
        r1 = self.session.post(url_step1, data=payload1)
        self.logger(f"  Step 1 (Ruolo Me Stesso): {r1.status_code}")
        
        if r1.status_code != 200:
             raise Exception(f"Errore selezione ruolo Me Stesso (Status {r1.status_code})")

        # Step 2: Estrazione PIVA dalla pagina di conferma
        # Cerchiamo la partita IVA nel testo della pagina (es. 07476680728)
        # Solitamente appare in un contesto tipo "Partita IVA del soggetto: 07476680728"
        piva_match = re.search(r'Partita IVA:\s*(\d{11})', r1.text)
        if not piva_match:
            # Fallback ricerca generica di 11 cifre se il label cambia
            piva_match = re.search(r'\b(\d{11})\b', r1.text)
            
        detected_piva = piva_match.group(1) if piva_match else "SCONOSCIUTA"
        self.logger(f"  PIVA rilevata dal portale: {detected_piva}")

        # Step 3: Finalizzazione (Navigazione verso la Home)
        r3 = self.session.get("https://ivaservizi.agenziaentrate.gov.it/portale/web/guest/home")
        self.logger(f"  Step 3 (Accesso Dashboard): {r3.status_code}")
        
        return detected_piva
