#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List

from app.engine import FEScraperEngine, unix_ms
from app.output_manager import OutputManager

LOG_FILE = "log_esecuzione.txt"

def load_env(path: str = ".env") -> Dict[str, str]:
    env_data: Dict[str, str] = {}
    if not os.path.exists(path):
        return env_data
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_data[k.strip()] = v.strip()
    return env_data

def logger(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts} - {message}\n")
    print(message)

def parse_inputs() -> Dict[str, str]:
    # 1. Determinazione file .env da caricare
    env_file = ".env"
    utenza_override = None
    
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        potential_env = "." + arg
        if os.path.exists(potential_env):
            env_file = potential_env
            print(f"Profilo caricato: {env_file}")
        else:
            # Se il file non esiste, l'argomento potrebbe essere l'UTENZA (1, 2, 3)
            # per mantenere la compatibilità con la versione precedente.
            utenza_override = arg

    env = load_env(env_file)
    cfg = {
        "CF": env.get("CF", ""),
        "PIN": env.get("PIN", ""),
        "PASSWORD": env.get("PASSWORD", ""),
        "PIVA": env.get("PIVA", ""),
        "DATA_DAL": env.get("DATA_DAL", ""),
        "DATA_AL": env.get("DATA_AL", ""),
        "TIPO": env.get("TIPO", "FOL"),
        "UTENZA": env.get("UTENZA", ""),
        "DAILY": env.get("DAILY", "0"),
        "DB": env.get("DB", "1"),
    }
    
    # 1.1 Gestione Automatismi Date (DAILY)
    if cfg["DAILY"] == "1":
        today = datetime.now().strftime("%d/%m/%Y")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
        cfg["DATA_DAL"] = yesterday
        cfg["DATA_AL"] = today
        print(f"Modalità DAILY attiva: impostata data dal {yesterday} al {today}")

    # 2. Priorità UTENZA: CLI > env file
    if utenza_override:
        cfg["UTENZA"] = utenza_override

    # 3. Controllo UTENZA da input interattivo (se ancora mancante)
    if not cfg["UTENZA"]:
        print("\n--- SELEZIONE UTENZA LAVORO ---")
        print("1. ME STESSO")
        print("2. DELEGA DIRETTA")
        print("3. INCARICATO")
        scelta = input("Inserisci il codice (1, 2 o 3): ").strip()
        cfg["UTENZA"] = scelta

    # Mappatura UTENZA -> MOTORE
    mapping = {
        "1": "ME_STESSO",
        "2": "DELEGA_DIRETTA",
        "3": "INTERMEDIARIO"
    }
    cfg["MOTORE"] = mapping.get(cfg["UTENZA"])
    
    if not cfg["MOTORE"]:
        print(f"Errore: Codice utenza '{cfg['UTENZA']}' non valido.")
        sys.exit(1)

    piva_required = (cfg["UTENZA"] != "1") # 1 = ME_STESSO
    
    if piva_required and not cfg["PIVA"]:
        print("Parametro PIVA mancante nel file .env.")
        sys.exit(1)

    if not all([cfg["CF"], cfg["PIN"], cfg["PASSWORD"], cfg["DATA_DAL"], cfg["DATA_AL"]]):
        print("Parametri mancanti nel file .env.")
        print("Assicurati che CF, PIN, PASSWORD, DATA_DAL, DATA_AL siano definiti.")
        sys.exit(1)
        
    return cfg

def main():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    cfg = parse_inputs()
    
    engine = FEScraperEngine(logger)

    try:
        json_dir = "JSON_extr"
        os.makedirs(json_dir, exist_ok=True)
        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        p_auth = engine.login(cfg["CF"], cfg["PIN"], cfg["PASSWORD"])
        
        # Selezione del motore e rilevamento PIVA operativa
        cfg["PIVA"] = engine.select_engine(cfg["MOTORE"], p_auth, cfg["PIVA"], cfg["TIPO"])
        
        # Inizializzazione Output con la PIVA corretta (rilevata o da env)
        output = OutputManager(cfg["PIVA"], logger, db_enabled=(cfg["DB"] == "1"))
        
        engine.get_b2b_tokens()

        # Download RICEVUTE
        data_ric = engine.fetch_invoices(cfg["DATA_DAL"], cfg["DATA_AL"], "RICEVUTE")
        ric_path = os.path.join(json_dir, f"fatture_ricevute_{run_ts}.json")
        with open(ric_path, "w", encoding="utf-8") as f:
            json.dump(data_ric, f, ensure_ascii=False, indent=2)
        stats_ric = {"found": 0, "downloaded": 0}
        if data_ric["totaleFatture"] > 0:
            stats_ric = output.download_invoices_set(
                engine.session, data_ric, "RICEVUTE", engine.headers_token, unix_ms
            )
        else:
            logger("Nessuna fattura RICEVUTA trovata.")

        # Download EMESSE
        data_eme = engine.fetch_invoices(cfg["DATA_DAL"], cfg["DATA_AL"], "EMESSE")
        eme_path = os.path.join(json_dir, f"fatture_emesse_{run_ts}.json")
        with open(eme_path, "w", encoding="utf-8") as f:
            json.dump(data_eme, f, ensure_ascii=False, indent=2)
        stats_eme = {"found": 0, "downloaded": 0}
        if data_eme["totaleFatture"] > 0:
            stats_eme = output.download_invoices_set(
                engine.session, data_eme, "EMESSE", engine.headers_token, unix_ms
            )
        else:
            logger("Nessuna fattura EMESSA trovata.")

        # Report Finale
        logger("\n" + "="*50)
        logger("RIEPILOGO PROCESSO")
        logger("="*50)
        
        if data_ric["totaleFatture"] > 0:
            output.final_check("RICEVUTE", stats_ric)
        if data_eme["totaleFatture"] > 0:
            output.final_check("EMESSE", stats_eme)

        logger(f"\nProcesso terminato. Log: {LOG_FILE}")

    except Exception as e:
        logger(f"ERRORE CRITICO: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
