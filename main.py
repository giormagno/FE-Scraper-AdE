#!/usr/bin/env python3
import os
import sys
import json
import shutil
from datetime import datetime, timedelta
from typing import Dict, List

from app.database import configure_database
from app.engine import FEScraperEngine, unix_ms
from app.output_manager import OutputManager

LOG_FILE = "log_esecuzione.txt"
ENV_DIR = "aziende"
LOG_DIR = os.path.join("output", "logs")
CURRENT_LOG_FILE = LOG_FILE

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
    return os.path.join(LOG_DIR, f"log_{token}.txt")


def set_active_log_file(env_file: str) -> str:
    global CURRENT_LOG_FILE
    CURRENT_LOG_FILE = get_log_file_path(env_file)
    log_dir = os.path.dirname(CURRENT_LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    return CURRENT_LOG_FILE


def discover_env_files() -> List[str]:
    if not os.path.isdir(ENV_DIR):
        return []

    env_files: List[str] = []
    for name in os.listdir(ENV_DIR):
        path = os.path.join(ENV_DIR, name)
        if not os.path.isfile(path):
            continue
        if name == ".env" or name.startswith(".env."):
            env_files.append(path)

    env_files.sort(key=lambda path: (os.path.basename(path) != ".env", os.path.basename(path)))
    return env_files


def resolve_env_file(arg: str) -> str | None:
    candidates: List[str] = []

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

    return None


def resolve_run_targets() -> List[Dict[str, object]]:
    args = sys.argv[1:]
    env_files = discover_env_files()

    if args:
        arg = args[0].strip()
        if arg.lower() == "all":
            if not env_files:
                raise ValueError(
                    f"Nessun profilo trovato nella cartella {ENV_DIR}/. "
                    "Aggiungi file come .env.azienda1, .env.azienda2, ..."
                )
            print(f"Modalita' multi-profilo: rilevati {len(env_files)} profili in {ENV_DIR}/")
            return [{"env_file": env_file, "allow_prompt": False} for env_file in env_files]

        env_file = resolve_env_file(arg)
        if env_file:
            print(f"Profilo caricato: {profile_display_name(env_file)}")
            return [{"env_file": env_file, "allow_prompt": True}]

        return [{"env_file": ".env", "utenza_override": arg, "allow_prompt": True}]

    if env_files:
        print(f"Modalita' multi-profilo: rilevati {len(env_files)} profili in {ENV_DIR}/")
        return [{"env_file": env_file, "allow_prompt": False} for env_file in env_files]

    if os.path.isfile(".env"):
        return [{"env_file": ".env", "allow_prompt": True}]

    raise ValueError(
        "Nessun file di configurazione trovato. Usa .env oppure crea profili in aziende/ "
        "con nomi come .env.azienda1, .env.azienda2, ..."
    )


def get_failure_store_path(json_dir: str, piva: str) -> str:
    return os.path.join(json_dir, f"download_failures_{piva}.json")


def empty_failure_store(piva: str) -> Dict[str, object]:
    return {
        "piva": piva,
        "updated_at": "",
        "categories": {
            "RICEVUTE": [],
            "EMESSE": [],
        },
    }


def failure_key(item: Dict[str, object]) -> tuple:
    return (
        str(item.get("category", "")),
        str(item.get("idFattura", "")),
        str(item.get("tipoInvio", "")),
        str(item.get("tipoFile", "FILE_FATTURA")),
    )


def load_failure_store(path: str, piva: str) -> Dict[str, object]:
    store = empty_failure_store(piva)
    if not os.path.exists(path):
        return store

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return store

    categories = data.get("categories")
    if "categories" in data and isinstance(categories, dict):
        store["updated_at"] = str(data.get("updated_at", ""))
        store["piva"] = str(data.get("piva", piva))
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
                store["categories"][category] = normalized_items
        return store

    # Compatibilita' con il vecchio formato single-run.
    category = data.get("category")
    failed_struct = data.get("failed_struct", [])
    if category in ("RICEVUTE", "EMESSE") and isinstance(failed_struct, list):
        normalized_items = []
        for item in failed_struct:
            if not isinstance(item, dict):
                continue
            normalized = dict(item)
            normalized["category"] = category
            normalized["tipoFile"] = str(normalized.get("tipoFile", "FILE_FATTURA"))
            normalized_items.append(normalized)
        store["categories"][category] = normalized_items
    return store


def save_failure_store(path: str, store: Dict[str, object]) -> None:
    categories = store.get("categories", {})
    if not isinstance(categories, dict):
        categories = {}

    for category in ("RICEVUTE", "EMESSE"):
        items = categories.get(category, [])
        if isinstance(items, list):
            categories[category] = sorted(
                [item for item in items if isinstance(item, dict)],
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


def collect_failed_entries(stats: Dict[str, object], category: str, run_ts: str) -> List[Dict[str, object]]:
    failed_struct = stats.get("failed_struct", [])
    if not isinstance(failed_struct, list):
        return []

    entries: List[Dict[str, object]] = []
    for item in failed_struct:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized["category"] = category
        normalized["tipoFile"] = str(normalized.get("tipoFile", "FILE_FATTURA"))
        normalized["first_seen"] = run_ts
        normalized["last_seen"] = run_ts
        normalized["attempts"] = 1
        entries.append(normalized)
    return entries


def merge_failure_entries(
    existing_entries: List[Dict[str, object]],
    new_entries: List[Dict[str, object]],
    run_ts: str,
) -> List[Dict[str, object]]:
    merged = {
        failure_key(item): dict(item)
        for item in existing_entries
        if isinstance(item, dict)
    }

    for item in new_entries:
        key = failure_key(item)
        if key in merged:
            current = merged[key]
            current["status"] = item.get("status", current.get("status"))
            current["url"] = item.get("url", current.get("url"))
            current["last_seen"] = run_ts
            current["attempts"] = int(current.get("attempts", 1)) + 1
            merged[key] = current
        else:
            merged[key] = dict(item)

    return list(merged.values())


def build_retry_data(entries: List[Dict[str, object]]) -> Dict[str, object]:
    fatture = []
    seen = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("idFattura", "")), str(item.get("tipoInvio", "")))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        fatture.append({
            "idFattura": key[0],
            "tipoInvio": key[1],
        })
    return {
        "totaleFatture": len(fatture),
        "fatture": fatture,
    }


def apply_retry_results(
    pending_entries: List[Dict[str, object]],
    retry_stats: Dict[str, object],
    run_ts: str,
) -> tuple[List[Dict[str, object]], set[tuple]]:
    failed_struct = retry_stats.get("failed_struct", [])
    failed_map = {}
    if isinstance(failed_struct, list):
        failed_map = {
            failure_key(item): item
            for item in failed_struct
            if isinstance(item, dict)
        }

    remaining = []
    recovered_keys = set()
    for item in pending_entries:
        key = failure_key(item)
        if key not in failed_map:
            recovered_keys.add(key)
            continue

        updated = dict(item)
        latest = failed_map[key]
        updated["status"] = latest.get("status", updated.get("status"))
        updated["url"] = latest.get("url", updated.get("url"))
        updated["last_seen"] = run_ts
        updated["attempts"] = int(updated.get("attempts", 1)) + 1
        remaining.append(updated)

    return remaining, recovered_keys


def has_pending_failures(store: Dict[str, object]) -> bool:
    categories = store.get("categories", {})
    if not isinstance(categories, dict):
        return False
    for category in ("RICEVUTE", "EMESSE"):
        items = categories.get(category, [])
        if isinstance(items, list) and items:
            return True
    return False


def cleanup_output_root(root_path: str) -> None:
    if os.path.isdir(root_path):
        shutil.rmtree(root_path)
        logger(f"WRITE=0: rimossa cartella di output temporanea {root_path}")

def parse_inputs(
    env_file: str = ".env",
    utenza_override: str | None = None,
    allow_prompt: bool = True,
) -> Dict[str, str]:
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
        "WRITE": env.get("WRITE", "1"),
        "ENV_FILE": env_file,
        "PROFILE_NAME": profile_display_name(env_file),
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
        if allow_prompt:
            print("\n--- SELEZIONE UTENZA LAVORO ---")
            print("1. ME STESSO")
            print("2. DELEGA DIRETTA")
            print("3. INCARICATO")
            scelta = input("Inserisci il codice (1, 2 o 3): ").strip()
            cfg["UTENZA"] = scelta
        else:
            raise ValueError(
                f"Parametro UTENZA mancante nel profilo {cfg['PROFILE_NAME']}. "
                "Per l'esecuzione batch dentro aziende/ il campo UTENZA deve essere valorizzato."
            )

    # Mappatura UTENZA -> MOTORE
    mapping = {
        "1": "ME_STESSO",
        "2": "DELEGA_DIRETTA",
        "3": "INTERMEDIARIO"
    }
    cfg["MOTORE"] = mapping.get(cfg["UTENZA"])
    
    if not cfg["MOTORE"]:
        raise ValueError(
            f"Codice utenza '{cfg['UTENZA']}' non valido nel profilo {cfg['PROFILE_NAME']}."
        )

    piva_required = (cfg["UTENZA"] != "1") # 1 = ME_STESSO
    
    if piva_required and not cfg["PIVA"]:
        raise ValueError(f"Parametro PIVA mancante nel profilo {cfg['PROFILE_NAME']}.")

    if not all([cfg["CF"], cfg["PIN"], cfg["PASSWORD"], cfg["DATA_DAL"], cfg["DATA_AL"]]):
        raise ValueError(
            f"Parametri mancanti nel profilo {cfg['PROFILE_NAME']}. "
            "Assicurati che CF, PIN, PASSWORD, DATA_DAL, DATA_AL siano definiti."
        )
        
    return cfg

def run_profile(cfg: Dict[str, str], profile_index: int, total_profiles: int) -> bool:
    profile_name = str(cfg.get("PROFILE_NAME", cfg.get("ENV_FILE", ".env")))
    log_path = CURRENT_LOG_FILE

    logger("\n" + "=" * 70)
    if total_profiles > 1:
        logger(f"AVVIO PROFILO [{profile_index}/{total_profiles}] {profile_name}")
    else:
        logger(f"AVVIO PROFILO {profile_name}")
    logger("=" * 70)
    logger(f"Log profilo: {log_path}")

    configure_database(cfg["ENV_FILE"])

    engine = FEScraperEngine(logger)

    try:
        json_dir = os.path.join("output", "JSON_extr")
        os.makedirs(json_dir, exist_ok=True)
        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        p_auth = engine.login(cfg["CF"], cfg["PIN"], cfg["PASSWORD"])
        
        # Selezione del motore e rilevamento PIVA operativa
        cfg["PIVA"] = engine.select_engine(cfg["MOTORE"], p_auth, cfg["PIVA"], cfg["TIPO"])

        failure_store_path = get_failure_store_path(json_dir, cfg["PIVA"])
        failure_store = load_failure_store(failure_store_path, cfg["PIVA"])
        pending_before_run = {
            category: [dict(item) for item in failure_store["categories"].get(category, [])]
            for category in ("RICEVUTE", "EMESSE")
        }
        
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

        recovered_keys_by_category = {"RICEVUTE": set(), "EMESSE": set()}

        for category in ("RICEVUTE", "EMESSE"):
            pending_items = pending_before_run.get(category, [])
            if not pending_items:
                continue

            logger(
                f"Retry {category}: tentativo di recupero per {len(pending_items)} fatture pendenti "
                f"dal file {os.path.basename(failure_store_path)}"
            )
            retry_data = build_retry_data(pending_items)
            retry_stats = output.download_invoices_set(
                engine.session, retry_data, category, engine.headers_token, unix_ms
            )
            remaining_items, recovered_keys = apply_retry_results(pending_items, retry_stats, run_ts)
            recovered = len(pending_items) - len(remaining_items)
            logger(f"Retry {category}: recuperate {recovered}, ancora pendenti {len(remaining_items)}")
            failure_store["categories"][category] = remaining_items
            recovered_keys_by_category[category] = recovered_keys

        failure_store["categories"]["RICEVUTE"] = merge_failure_entries(
            failure_store["categories"]["RICEVUTE"],
            [
                item
                for item in collect_failed_entries(stats_ric, "RICEVUTE", run_ts)
                if failure_key(item) not in recovered_keys_by_category["RICEVUTE"]
            ],
            run_ts,
        )
        failure_store["categories"]["EMESSE"] = merge_failure_entries(
            failure_store["categories"]["EMESSE"],
            [
                item
                for item in collect_failed_entries(stats_eme, "EMESSE", run_ts)
                if failure_key(item) not in recovered_keys_by_category["EMESSE"]
            ],
            run_ts,
        )

        if has_pending_failures(failure_store):
            save_failure_store(failure_store_path, failure_store)
            logger(
                f"File pendenti aggiornato: {os.path.basename(failure_store_path)} "
                f"(RICEVUTE={len(failure_store['categories']['RICEVUTE'])}, "
                f"EMESSE={len(failure_store['categories']['EMESSE'])})"
            )
        elif os.path.exists(failure_store_path):
            os.remove(failure_store_path)
            logger(f"Nessun download pendente: rimosso {os.path.basename(failure_store_path)}")

        # Report Finale
        logger("\n" + "="*50)
        logger("RIEPILOGO PROCESSO")
        logger("="*50)
        
        if data_ric["totaleFatture"] > 0:
            output.final_check("RICEVUTE", stats_ric)
        if data_eme["totaleFatture"] > 0:
            output.final_check("EMESSE", stats_eme)

        if cfg["WRITE"] == "0":
            cleanup_output_root(output.root_path)

        logger(f"\nProfilo completato: {profile_name}")
        logger(f"Processo terminato. Log: {log_path}")
        return True

    except Exception as e:
        logger(f"ERRORE CRITICO [{profile_name}]: {e}")
        return False

def main():
    try:
        targets = resolve_run_targets()
    except ValueError as e:
        print(f"Errore: {e}")
        sys.exit(1)

    total_profiles = len(targets)
    failures = 0

    for index, target in enumerate(targets, start=1):
        target_env = str(target.get("env_file", ".env"))
        log_path = set_active_log_file(target_env)
        try:
            cfg = parse_inputs(
                env_file=target_env,
                utenza_override=target.get("utenza_override"),
                allow_prompt=bool(target.get("allow_prompt", True)),
            )
        except Exception as e:
            profile_name = profile_display_name(target_env)
            logger("\n" + "=" * 70)
            if total_profiles > 1:
                logger(f"AVVIO PROFILO [{index}/{total_profiles}] {profile_name}")
            else:
                logger(f"AVVIO PROFILO {profile_name}")
            logger("=" * 70)
            logger(f"Log profilo: {log_path}")
            logger(f"ERRORE CRITICO [{profile_name}]: {e}")
            failures += 1
            continue

        if not run_profile(cfg, index, total_profiles):
            failures += 1

    if total_profiles > 1:
        print("\n" + "=" * 70)
        print(
            f"ESECUZIONE MULTI-PROFILO COMPLETATA: "
            f"{total_profiles - failures} profili OK, {failures} in errore."
        )
        print("=" * 70)

    if failures > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
