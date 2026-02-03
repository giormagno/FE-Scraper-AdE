import os
import re
import base64
from datetime import datetime
from typing import Dict, List, Any, Optional
from asn1crypto import cms
from app.processor import process_xml_file

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

def unix_ms() -> str:
    from app.engine import unix_ms as engine_unix_ms # Evita import ciclici se necessario, o sposta in utils
    return engine_unix_ms()

def ensure_dirs(*paths: str) -> None:
    for p in paths:
        os.makedirs(p, exist_ok=True)

def safe_filename_from_disposition(disposition: str, fallback: str) -> str:
    m = re.findall(r"filename=(.+)", disposition or "")
    return m[0].strip('"') if m else fallback

def extract_xml_from_p7m(content: bytes, filename: str, logger_func) -> Optional[bytes]:
    try:
        try:
            content_info = cms.ContentInfo.load(content)
        except Exception:
            if content.strip().startswith(b"<"):
                return content
            decoded = base64.b64decode(content)
            content_info = cms.ContentInfo.load(decoded)

        payload = content_info["content"]["encap_content_info"]["content"].native
        return payload

    except Exception as e:
        logger_func(f"Errore estrazione P7M per il file {filename}: {e}")
        return None

class OutputManager:
    def __init__(self, piva: str, logger_func, db_enabled: bool = True):
        self.piva = piva
        self.logger = logger_func
        self.db_enabled = db_enabled
        # Cartella PartitaIVA_FE invece di Ricevute_partitaIVA
        self.root_path = f"{piva}_FE"
        ensure_dirs(self.root_path)
        
        # Statistiche Database (cumulate per tutta la sessione)
        self.db_stats = {
            "ADDED": 0,
            "SKIPPED": 0,
            "ERROR": 0
        }

    def _handle_db_hook(self, xml_path: str):
        if self.db_enabled:
            status = process_xml_file(xml_path)
            if status in self.db_stats:
                self.db_stats[status] += 1

    def download_invoices_set(
        self,
        session,
        data: Dict[str, Any],
        category: str, # "RICEVUTE" or "EMESSE"
        headers_token: Dict[str, str],
        unix_ms_func
    ) -> Dict[str, Any]:
        
        base_path = os.path.join(self.root_path, category)
        path_orig = os.path.join(base_path, "ORIGINALI")
        path_info = os.path.join(base_path, "INFO")
        path_fatt = os.path.join(base_path, "FATTURE")
        ensure_dirs(path_orig, path_info, path_fatt)

        total = int(data.get("totaleFatture", 0))
        stats: Dict[str, Any] = {
            "found": total, 
            "downloaded": 0, 
            "failed": [], 
            "p7m_errors": []
        }

        self.logger(f"Inizio download {category}: {total} fatture trovate.")

        invoices = data.get("fatture", [])
        iterator = enumerate(invoices, 1)
        if tqdm:
            iterator = tqdm(iterator, total=total, desc=f"Download {category}", unit="fatt", ascii=True)

        for _, fattura in iterator:
            fattura_file = f"{fattura['tipoInvio']}{fattura['idFattura']}"

            # 1) Scarico FILE_FATTURA
            try:
                url = (
                    "https://ivaservizi.agenziaentrate.gov.it/cons/cons-services/rs/fatture/file/"
                    f"{fattura_file}?tipoFile=FILE_FATTURA&download=1&v={unix_ms_func()}"
                )
                r = session.get(url, headers=headers_token, stream=True)

                if r.status_code != 200:
                    stats["failed"].append(f"{fattura_file} (Status {r.status_code})")
                    continue

                fname = safe_filename_from_disposition(r.headers.get("content-disposition", ""), f"file_{fattura_file}")
                content = r.content

                is_metadata = fname.lower().startswith("informazioni_associate")

                # Bug fix: Metadati solo in INFO, non in ORIGINALI
                if is_metadata:
                    with open(os.path.join(path_info, fname), "wb") as f:
                        f.write(content)
                else:
                    # Salva l'originale se non è metadato
                    with open(os.path.join(path_orig, fname), "wb") as f:
                        f.write(content)

                    # Estrazione XML se è P7M
                    if fname.lower().endswith(".p7m"):
                        xml_content = extract_xml_from_p7m(content, fname, self.logger)
                        if xml_content:
                            xml_name = fname.lower().replace(".p7m", "")
                            if not xml_name.endswith(".xml"):
                                xml_name += ".xml"
                            xml_path = os.path.join(path_fatt, xml_name)
                            with open(xml_path, "wb") as f:
                                f.write(xml_content)
                            # Hook per il database
                            self._handle_db_hook(xml_path)
                        else:
                            stats["p7m_errors"].append(fname)

                    # Salvo direttamente se è XML
                    elif fname.lower().endswith(".xml"):
                        xml_path = os.path.join(path_fatt, fname)
                        with open(xml_path, "wb") as f:
                            f.write(content)
                        # Hook per il database
                        self._handle_db_hook(xml_path)

                stats["downloaded"] += 1

            except Exception as e:
                stats["failed"].append(f"{fattura_file} (Errore: {e})")

            # 2) Scarico FILE_METADATI (opzionale)
            try:
                url_meta = (
                    "https://ivaservizi.agenziaentrate.gov.it/cons/cons-services/rs/fatture/file/"
                    f"{fattura_file}?tipoFile=FILE_METADATI&download=1&v={unix_ms_func()}"
                )
                r = session.get(url_meta, headers=headers_token, stream=True)
                if r.status_code == 200:
                    fname = safe_filename_from_disposition(
                        r.headers.get("content-disposition", ""), f"meta_{fattura_file}"
                    )
                    content = r.content
                    
                    # Fix: sempre in INFO, mai in ORIGINALI
                    with open(os.path.join(path_info, fname), "wb") as f:
                        f.write(content)
            except Exception:
                pass 

        return stats

    def final_check(self, category: str, stats: Dict[str, Any]):
        """Verifica file su disco e segnala discrepanze."""
        final_dir = os.path.join(self.root_path, category, "FATTURE")
        orig_dir = os.path.join(self.root_path, category, "ORIGINALI")
        
        if not os.path.exists(final_dir):
            self.logger(f"  ⚠️ Cartella {final_dir} non trovata!")
            return

        files_on_disk = [f for f in os.listdir(final_dir) if f.lower().endswith(".xml")]
        orig_files = [f for f in os.listdir(orig_dir)]
        
        count_disk = len(files_on_disk)

        self.logger(f"\n--- RIEPILOGO {category} ---")
        self.logger(f"Fatture trovate sul portale: {stats['found']}")
        self.logger(f"Fatture scaricate (files):   {stats['downloaded']}")
        self.logger(f"Fatture XML totali su disco: {count_disk}")

        # Identificazione file mancanti
        if stats['found'] > count_disk:
            self.logger(f"  ⚠️ ATTENZIONE: Mancano {stats['found'] - count_disk} file XML!")
            
            missing = []
            for f_orig in orig_files:
                expected_xml = f_orig.lower().replace(".p7m", "").replace(".xml", "") + ".xml"
                if expected_xml not in [fn.lower() for fn in files_on_disk]:
                    missing.append(f_orig)
            
            if missing:
                self.logger("  Fatture presenti in ORIGINALI ma non convertite in XML:")
                for m in missing:
                    self.logger(f"    - {m}")

        err_count = len(stats.get("failed", [])) + len(stats.get("p7m_errors", []))
        if err_count:
            self.logger(f"Errori riscontrati durante il download: {err_count}")
            for fail in stats.get("failed", []):
                self.logger(f"  [DOWNLOAD KO] {fail}")
            for p7m_fail in stats.get("p7m_errors", []):
                self.logger(f"  [ESTRAZIONE P7M KO] {p7m_fail}")

        # Summary Database specifico per questa categoria
        # Nota: self.db_stats è cumulativo, ma qui ci interessa dare un feedback
        if self.db_enabled:
            self.logger("\n--- STATISTICHE DATABASE (Totale sessione) ---")
            self.logger(f"Nuove fatture inserite:   {self.db_stats['ADDED']}")
            self.logger(f"Fatture saltate (dupl.):  {self.db_stats['SKIPPED']}")
            if self.db_stats['ERROR'] > 0:
                self.logger(f"⚠️ Errori durante l'inserimento: {self.db_stats['ERROR']}")
            else:
                self.logger("Nessun errore riscontrato nel Database.")
