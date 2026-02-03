import re
import requests
from app.engine import unix_ms

class IntermediarioEngine:
    """
    Motore specifico per la gestione degli incarichi come Intermediario (Incaricato).
    Separato per modularità e facilità di aggiornamento dei payload SDI.
    """
    def __init__(self, session: requests.Session, logger_func):
        self.session = session
        self.logger = logger_func

    def run_selection(self, p_auth: str, piva: str, sdi_role: str):
        """
        Esegue la catena di richieste per selezionare il ruolo incaricato 
        e inserire la PIVA del cliente.
        """
        self.logger(f"Inizio procedura Incaricato per cliente {piva}")
        
        # Step 1: Selezione ruolo "Incaricato"
        url_base = (
            "https://ivaservizi.agenziaentrate.gov.it/portale/scelta-utenza-lavoro"
            f"?p_auth={p_auth}"
            "&p_p_id=SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet"
            "&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1"
        )
        
        url_step1 = f"{url_base}&_SceltaUtenzaLavoro_WAR_SceltaUtenzaLavoroportlet_javax.portlet.action=incarichiAction"
        payload1 = {"tipoutenza": "Incaricato"}
        
        r1 = self.session.post(url_step1, data=payload1)
        self.logger(f"  Step 1 (Ruolo Incaricato): {r1.status_code}")
        
        if r1.status_code != 200:
             raise Exception(f"Errore selezione ruolo Incaricato (Status {r1.status_code})")

        # Step 1.1: Auto-rilevamento suffisso (FOL/ENT) dal dropdown
        # Cerchiamo nel HTML della risposta l'opzione che contiene la PIVA
        # Formato atteso: <option value="07757690727-FOL">...
        options = re.findall(rf'value="({piva}-[A-Z0-9]+)"', r1.text)
        
        if options:
            scelta_val = options[0]
            self.logger(f"  Auto-rilevamento: trovato valore '{scelta_val}' nel portale.")
        else:
            # Fallback se non trovato nel HTML (usa sdi_role da configurazione)
            scelta_val = f"{piva}-{sdi_role}"
            self.logger(f"  Attenzione: PIVA non trovata nel dropdown. Fallback su: {scelta_val}")

        # Step 2: Selezione Soggetto (PIVA)
        payload2 = {
            "sceltaincarico": scelta_val,
            "tipoincaricante": "incDiretto"
        }
        
        r2 = self.session.post(url_step1, data=payload2)
        self.logger(f"  Step 2 (Selezione Soggetto {scelta_val}): {r2.status_code}")
        
        if r2.status_code != 200:
             raise Exception(f"Errore selezione soggetto delegante (Status {r2.status_code})")

        # Step 3: Finalizzazione (Navigazione verso la Home)
        r3 = self.session.get("https://ivaservizi.agenziaentrate.gov.it/portale/web/guest/home")
        self.logger(f"  Step 3 (Accesso Dashboard): {r3.status_code}")
        
        if r3.status_code != 200:
            self.logger("  Attenzione: La navigazione finale alla dashboard ha restituito un codice non 200.")

        self.logger("Procedura Incaricato completata con successo.")
