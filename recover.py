#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime

from app.engine import FEScraperEngine, unix_ms
from app.output_manager import OutputManager

LOG_FILE = "log_recover.txt"


def logger(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts} - {message}\n")
    print(message)


def load_env(path: str) -> dict:
    env_data = {}
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


def parse_cfg(env_file: str) -> dict:
    env = load_env(env_file)
    cfg = {
        "CF": env.get("CF", ""),
        "PIN": env.get("PIN", ""),
        "PASSWORD": env.get("PASSWORD", ""),
        "PIVA": env.get("PIVA", ""),
        "TIPO": env.get("TIPO", "FOL"),
        "UTENZA": env.get("UTENZA", ""),
        "DB": env.get("DB", "1"),
    }

    mapping = {
        "1": "ME_STESSO",
        "2": "DELEGA_DIRETTA",
        "3": "INTERMEDIARIO",
    }
    cfg["MOTORE"] = mapping.get(cfg["UTENZA"])

    if not cfg["MOTORE"]:
        print(f"Errore: Codice utenza '{cfg['UTENZA']}' non valido.")
        sys.exit(1)

    piva_required = (cfg["UTENZA"] != "1")  # 1 = ME_STESSO
    if piva_required and not cfg["PIVA"]:
        print("Parametro PIVA mancante nel file .env.")
        sys.exit(1)

    if not all([cfg["CF"], cfg["PIN"], cfg["PASSWORD"]]):
        print("Parametri mancanti nel file .env.")
        print("Assicurati che CF, PIN, PASSWORD siano definiti.")
        sys.exit(1)

    return cfg


def load_failures(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    failed = data.get("failed", [])
    if not isinstance(failed, list):
        return []
    return failed


def group_by_category(failures: list) -> dict:
    grouped = {}
    for item in failures:
        if not isinstance(item, dict):
            continue
        cat = item.get("category")
        if not cat:
            continue
        grouped.setdefault(cat, []).append(item)
    return grouped


def to_fattura_list(items: list) -> list:
    fatture = []
    for it in items:
        id_fattura = it.get("idFattura")
        tipo_invio = it.get("tipoInvio")
        if not id_fattura or not tipo_invio:
            continue
        fatture.append({
            "idFattura": id_fattura,
            "tipoInvio": tipo_invio,
        })
    return fatture


def main():
    parser = argparse.ArgumentParser(description="Recupero download falliti da JSON locale.")
    parser.add_argument("failures_json", help="Percorso al file download_failures_struct.json")
    parser.add_argument("--env", default=".env", help="Percorso file .env (default: .env)")
    args = parser.parse_args()

    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    cfg = parse_cfg(args.env)
    failures = load_failures(args.failures_json)
    grouped = group_by_category(failures)

    if not grouped:
        logger("Nessun fallimento valido trovato nel JSON.")
        return

    engine = FEScraperEngine(logger)
    p_auth = engine.login(cfg["CF"], cfg["PIN"], cfg["PASSWORD"])
    cfg["PIVA"] = engine.select_engine(cfg["MOTORE"], p_auth, cfg["PIVA"], cfg["TIPO"])
    output = OutputManager(cfg["PIVA"], logger, db_enabled=(cfg["DB"] == "1"))
    engine.get_b2b_tokens()

    for category, items in grouped.items():
        fatture = to_fattura_list(items)
        if not fatture:
            logger(f"Nessuna fattura valida da recuperare per {category}.")
            continue
        data = {"totaleFatture": len(fatture), "fatture": fatture}
        logger(f"Recupero {category}: {len(fatture)} fatture da JSON locale.")
        output.download_invoices_set(
            engine.session, data, category, engine.headers_token, unix_ms
        )


if __name__ == "__main__":
    main()
