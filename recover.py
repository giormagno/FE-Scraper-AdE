#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sys
from datetime import datetime

from app.engine import FEScraperEngine, unix_ms
from app.output_manager import OutputManager

LOG_FILE = "log_recover.txt"
ENV_DIR = "aziende"
LOG_DIR = os.path.join("output", "logs")
CURRENT_LOG_FILE = LOG_FILE


def logger(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CURRENT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts} - {message}\n")
    print(message)


def profile_display_name(env_file: str) -> str:
    normalized = os.path.normpath(env_file)
    if normalized == ".env":
        return ".env"
    if normalized.startswith(f"{ENV_DIR}{os.sep}"):
        return normalized
    return os.path.basename(normalized)


def sanitize_log_token(value: str) -> str:
    sanitized = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    sanitized = sanitized.strip("_")
    return sanitized or "profilo"


def get_log_file_path(env_file: str) -> str:
    normalized = os.path.normpath(env_file)
    if normalized == ".env":
        return LOG_FILE

    base_name = os.path.basename(normalized)
    if base_name == ".env":
        token = "env_default"
    elif base_name.startswith(".env."):
        token = base_name[len(".env."):]
    else:
        token = base_name.lstrip(".")

    token = sanitize_log_token(token)
    return os.path.join(LOG_DIR, f"log_recover_{token}.txt")


def set_active_log_file(env_file: str) -> str:
    global CURRENT_LOG_FILE
    CURRENT_LOG_FILE = get_log_file_path(env_file)
    log_dir = os.path.dirname(CURRENT_LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    return CURRENT_LOG_FILE


def resolve_env_file(arg: str) -> str:
    candidates = []
    if os.path.isfile(arg):
        candidates.append(arg)

    if arg.startswith(".env"):
        candidates.extend([arg, os.path.join(ENV_DIR, arg)])
    elif arg.startswith("."):
        candidates.extend([arg, os.path.join(ENV_DIR, arg)])
    else:
        candidates.extend([
            "." + arg,
            os.path.join(ENV_DIR, arg),
            os.path.join(ENV_DIR, f".env.{arg}"),
        ])

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if os.path.isfile(candidate):
            return candidate

    return arg


def get_failure_store_path(json_dir: str, piva: str) -> str:
    return os.path.join(json_dir, f"download_failures_{piva}.json")


def empty_failure_store(piva: str) -> dict:
    return {
        "piva": piva,
        "updated_at": "",
        "categories": {
            "RICEVUTE": [],
            "EMESSE": [],
        },
    }


def failure_key(item: dict) -> tuple:
    return (
        str(item.get("category", "")),
        str(item.get("idFattura", "")),
        str(item.get("tipoInvio", "")),
        str(item.get("tipoFile", "FILE_FATTURA")),
    )


def save_failure_store(path: str, store: dict) -> None:
    categories = store.get("categories", {})
    if not isinstance(categories, dict):
        categories = {}

    for category in ("RICEVUTE", "EMESSE"):
        items = categories.get(category, [])
        if isinstance(items, list):
            normalized_items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                normalized["category"] = category
                normalized["tipoFile"] = str(normalized.get("tipoFile", "FILE_FATTURA"))
                normalized_items.append(normalized)
            categories[category] = sorted(
                normalized_items,
                key=lambda item: (
                    str(item.get("idFattura", "")),
                    str(item.get("tipoInvio", "")),
                    str(item.get("tipoFile", "")),
                ),
            )
        else:
            categories[category] = []

    store["categories"] = categories
    store["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def has_pending_failures(store: dict) -> bool:
    categories = store.get("categories", {})
    if not isinstance(categories, dict):
        return False
    for category in ("RICEVUTE", "EMESSE"):
        items = categories.get(category, [])
        if isinstance(items, list) and items:
            return True
    return False


def apply_retry_results(items: list, stats: dict, category: str, run_ts: str) -> list:
    failed_struct = stats.get("failed_struct", [])
    failed_map = {}
    if isinstance(failed_struct, list):
        failed_map = {
            failure_key(item): item
            for item in failed_struct
            if isinstance(item, dict)
        }

    remaining = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized["category"] = category
        normalized["tipoFile"] = str(normalized.get("tipoFile", "FILE_FATTURA"))
        key = failure_key(normalized)
        if key not in failed_map:
            continue

        latest = failed_map[key]
        normalized["status"] = latest.get("status", normalized.get("status"))
        normalized["url"] = latest.get("url", normalized.get("url"))
        normalized["last_seen"] = run_ts
        normalized["attempts"] = int(normalized.get("attempts", 1)) + 1
        remaining.append(normalized)

    return remaining


def cleanup_output_root(root_path: str) -> None:
    if os.path.isdir(root_path):
        shutil.rmtree(root_path)
        logger(f"WRITE=0: rimossa cartella di output temporanea {root_path}")


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
        "WRITE": env.get("WRITE", "1"),
        "ENV_FILE": env_file,
        "PROFILE_NAME": profile_display_name(env_file),
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

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if not isinstance(data, dict):
        return []

    categories = data.get("categories")
    if "categories" in data and isinstance(categories, dict):
        failures = []
        for category, items in categories.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                normalized["category"] = normalized.get("category", category)
                failures.append(normalized)
        return failures

    failed_struct = data.get("failed_struct", [])
    if isinstance(failed_struct, list) and failed_struct and all(isinstance(item, dict) for item in failed_struct):
        return failed_struct

    failed = data.get("failed", [])
    if isinstance(failed, list):
        return [item for item in failed if isinstance(item, dict)]

    return []


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
    parser.add_argument("failures_json", help="Percorso al file JSON dei download falliti")
    parser.add_argument("--env", default=".env", help="Percorso file .env (default: .env)")
    args = parser.parse_args()

    resolved_env = resolve_env_file(args.env)
    log_path = set_active_log_file(resolved_env)

    cfg = parse_cfg(resolved_env)
    logger("\n" + "=" * 70)
    logger(f"AVVIO RECOVER PROFILO {cfg['PROFILE_NAME']}")
    logger("=" * 70)
    logger(f"Log profilo: {log_path}")
    failures = load_failures(args.failures_json)
    grouped = group_by_category(failures)

    if not grouped:
        logger("Nessun fallimento valido trovato nel JSON.")
        return

    json_dir = os.path.join("output", "JSON_extr")
    os.makedirs(json_dir, exist_ok=True)
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    engine = FEScraperEngine(logger)
    p_auth = engine.login(cfg["CF"], cfg["PIN"], cfg["PASSWORD"])
    cfg["PIVA"] = engine.select_engine(cfg["MOTORE"], p_auth, cfg["PIVA"], cfg["TIPO"])
    output = OutputManager(cfg["PIVA"], logger, db_enabled=(cfg["DB"] == "1"))
    engine.get_b2b_tokens()

    failure_store_path = get_failure_store_path(json_dir, cfg["PIVA"])
    updated_store = empty_failure_store(cfg["PIVA"])

    for category, items in grouped.items():
        fatture = to_fattura_list(items)
        if not fatture:
            logger(f"Nessuna fattura valida da recuperare per {category}.")
            continue
        data = {"totaleFatture": len(fatture), "fatture": fatture}
        logger(f"Recupero {category}: {len(fatture)} fatture da JSON locale.")
        stats = output.download_invoices_set(
            engine.session, data, category, engine.headers_token, unix_ms
        )
        remaining_items = apply_retry_results(items, stats, category, run_ts)
        updated_store["categories"][category] = remaining_items
        recovered = len(items) - len(remaining_items)
        logger(f"Recupero {category}: recuperate {recovered}, ancora pendenti {len(remaining_items)}")

    if has_pending_failures(updated_store):
        save_failure_store(failure_store_path, updated_store)
        logger(
            f"File pendenti aggiornato: {os.path.basename(failure_store_path)} "
            f"(RICEVUTE={len(updated_store['categories']['RICEVUTE'])}, "
            f"EMESSE={len(updated_store['categories']['EMESSE'])})"
        )
    elif os.path.exists(failure_store_path):
        os.remove(failure_store_path)
        logger(f"Nessun download pendente: rimosso {os.path.basename(failure_store_path)}")

    if cfg["WRITE"] == "0":
        cleanup_output_root(output.root_path)

    logger(f"Recover completato. Log: {log_path}")


if __name__ == "__main__":
    main()
