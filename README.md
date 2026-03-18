# FE Scraper - Downloader Fatture Elettroniche
**Aggiornato il: 18/03/2026**

FE Scraper è un tool Python avanzato per l'automazione del download delle fatture elettroniche (emesse e ricevute) dal portale dell'Agenzia delle Entrate. Supporta l'estrazione automatica da file P7M, l'organizzazione in cartelle strutturate e il salvataggio dei dati completi in un database (SQLite o MySQL) per una facile consultazione.

## Struttura del progetto

Il progetto è organizzato come segue:

- `main.py`: Punto di ingresso dell'applicazione. Gestisce il flusso principale, il caricamento della configurazione e l'interazione CLI.
- `app/`: Cartella contenente la logica core dell'applicazione.
    - `engine.py`: Gestisce le sessioni HTTP, l'autenticazione tramite scraping e il recupero dei token B2B.
    - `engine_mestesso.py` / `engine_intermediario.py`: Moduli specializzati per i diversi tipi di accesso (Me Stesso, Intermediario).
    - `output_manager.py`: Organizza i file scaricati in cartelle, gestisce l'estrazione del contenuto XML dai file firmati `.p7m`.
    - `processor.py`: Si occupa del parsing dei file XML e dell'inserimento dei dati nel database.
    - `database.py`: Definisce lo schema del database SQLite tramite SQLAlchemy.
- `.env`: File di configurazione per le credenziali e i parametri di esecuzione.
- `requirements.txt`: Elenco delle dipendenze Python necessarie.
- `fatture_v3.db`: Database SQLite locale (creato automaticamente al primo avvio) contenente i dati estratti dalle fatture.
- `recover.py`: Script di recupero download falliti a partire da un JSON locale.
- `Dockerfile` / `docker-compose.yml`: File per l'esecuzione del servizio tramite Docker.
- `entrypoint.sh`: Script di gestione loop per esecuzione continua in container.

## Accessi e Gestione

L'applicazione utilizza un file di configurazione (default `.env`) per gestire:
- **Credenziali AdE**: Codice Fiscale, PIN e Password per l'accesso al portale "Fatture e Corrispettivi".
- **Parametri Operativi**: Partita IVA di destinazione, range temporale (`DATA_DAL`, `DATA_AL`), tipo di utenza e attivazione/disattivazione database.

Il database SQLite (`fatture_v3.db`) viene inizializzato automaticamente e contiene tabelle dettagliate per anagrafiche, dati generali, righe di dettaglio, pagamenti, DDT e riferimenti a ordini/contratti.

## Tipologia e formato input

- **Configurazione**: File di testo in formato `.env` (chiave=valore).
- **Argomenti CLI**: È possibile passare il nome di un file di configurazione alternativo come argomento (es. `python main.py mioxml` caricherà il file `.mioxml`).
- **Interazione**: Se non specificato nel file `.env`, l'app richiederà interattivamente il tipo di utenza (Me Stesso, Delega Diretta, Incaricato).

## Tipologia e formato output

L'output viene generato nella cartella `{PIVA}_FE/`, suddivisa in:
- `RICEVUTE/` ed `EMESSE/`:
    - `ORIGINALI/`: Contiene i file originali scaricati dal portale (XML o P7M).
    - `INFO/`: Contiene i metadati e le informazioni associate fornite dall'AdE.
    - `FATTURE/`: Contiene esclusivamente i file in formato XML (estratti se originariamente P7M).
- **Database**: Dati strutturati salvati in `fatture_v3.db`.
- **JSON ricerca fatture**: In `JSON_extr/` vengono salvati i JSON completi delle fatture emesse/ricevute con timestamp.
- **Download falliti**: File `download_failures.json` e `download_failures_struct.json` per ogni categoria.
- **Log**: Report dettagliato dell'esecuzione in `log_esecuzione.txt`.

## Funzionalità aggiuntive

- **Estrazione P7M**: Conversione automatica dei file firmati in XML leggibile.
- **Supporto Multi-Database**: Supporta sia **SQLite** (file locale) che **MySQL** per il salvataggio dei dati.
- **Supporto Docker**: Configurazione pronta per avviare il tool come servizio continuo o on-demand.
- **Modalità Daily**: Configurando `DAILY=1`, l'app imposta automaticamente il range di ricerca tra ieri e oggi.
- **Gestione Chunk**: La ricerca viene suddivisa automaticamente in periodi di 3 mesi per superare i limiti temporali del portale AdE.
- **Deep Parsing**: Non solo download, ma estrazione di ogni dettaglio della fattura (incluse righe articolo e scadenze pagamenti).
- **Data Ricezione**: Per le ricevute viene salvata `dataConsegna`; per le emesse è impostata uguale alla data fattura.
- **Recovery**: Possibilità di riprovare i download falliti leggendo un JSON locale.

## Istruzioni sommarie

1. Configura il file `.env` con le tue credenziali.
2. Installa le dipendenze: `pip install -r requirements.txt`.
3. Avvia lo script: `python main.py`.
4. Controlla la cartella dei risultati e il database per i dati estratti.

Se si vuole automatizzare la procedura in modo tale che venga eseguita ogni giorno, leggi il paragrafo "Automatizza lo script" nel file `ISTRUZIONI.md`.

## Recupero download falliti

Usa `recover.py` passando il file `download_failures_struct.json` generato durante un run:

```bash
python recover.py /percorso/al/download_failures_struct.json
```

È possibile usare un file `.env` alternativo:

```bash
python recover.py /percorso/al/download_failures_struct.json --env .profilo
```
