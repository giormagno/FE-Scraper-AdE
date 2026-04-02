# FE Scraper - Downloader Fatture Elettroniche
FE Scraper è un tool Python avanzato per l'automazione del download delle fatture elettroniche (emesse e ricevute) dal portale dell'Agenzia delle Entrate. Supporta l'estrazione automatica da file P7M, l'organizzazione in cartelle strutturate e il salvataggio dei dati completi in un database (SQLite o MySQL) per una facile consultazione.

**UPDATE 02/04/2026**
> Il sistema è stato implementato al fine di effettuare il download delle fatture anche con il nuovo layout grafico del portale "Fatture e Corrispettivi" dell'Agenzia delle Entrate.
> 
> E' stato inoltre introdotto il retry automatico dei download pendenti: i fallimenti di `FILE_FATTURA` vengono salvati nel file `output/JSON_extr/download_failures_<PIVA>.json` e ritentati automaticamente nei run successivi.
> 
> Il progetto supporta ora anche la gestione multi-profilo tramite la cartella `aziende/`: se contiene file come `.env.azienda1`, `.env.azienda2`, `python main.py` li esegue automaticamente in serie sia in locale sia in Docker. Prendi spunto da env.example, crea una cartella `aziende` all'interno della repo e mettici tutti gli .env che vuoi!
> 
> I log sono stati separati per profilo: il profilo `.env` continua a usare `log_esecuzione.txt` e `log_recover.txt`, mentre i profili in `aziende/` scrivono in `output/logs/`.

**UPDATE 18/03/2026**
> L'aggiornamento del 18/03/2026 ha introdotto: 
> - la possibilità di eseguire lo script tramite **Docker**;
> - la compatibilità con il salvataggio dei dati in **MySQL**.

> Perchè queste modifiche?
> se hai già un database MySQL puoi creare un nuovo database e importare i dati delle fatture; se il tuo MySQL gira già su Docker, potrai ora collegare facilmente il database al container. In questo modo non dovrai più usare SQLite e potrai consultare i dati delle fatture da qualsiasi dispositivo connesso al database.
>
> Per far questo fai attenzione a condividere la stessa rete tra i due container, ad esempio usando la rete `shared-internal-net` (sia nel container di MySQL sia nel container di FE Scraper). In questo modo il container di FE Scraper potrà comunicare con il container di MySQL usando il nome del servizio come hostname.
> 
> E' stato aggiunto un markdown Campi_FE.md che riepiloga quali sono i campi della FE che vengono salvati all'interno del database.

## Struttura del progetto

Il progetto è organizzato come segue:

- `main.py`: Punto di ingresso dell'applicazione. Gestisce il flusso principale, il caricamento della configurazione e l'interazione CLI.
- `app/`: Cartella contenente la logica core dell'applicazione.
    - `engine.py`: Gestisce le sessioni HTTP, l'autenticazione IAMPE/portale, il recupero dei token B2B e il dispatch verso i motori specializzati.
    - `engine_delega.py` / `engine_mestesso.py` / `engine_intermediario.py`: Moduli specializzati per i diversi tipi di accesso (Delega Diretta, Me Stesso, Intermediario).
    - `output_manager.py`: Organizza i file scaricati in cartelle, gestisce l'estrazione del contenuto XML dai file firmati `.p7m` e il retry immediato dei download con status `304`/`503`.
    - `processor.py`: Si occupa del parsing dei file XML e dell'inserimento dei dati nel database.
    - `database.py`: Definisce lo schema del database SQLite tramite SQLAlchemy.
- `.env`: File di configurazione per le credenziali e i parametri di esecuzione.
- `aziende/`: Cartella opzionale contenente i profili multipli (`.env.azienda1`, `.env.azienda2`, ...).
- `requirements.txt`: Elenco delle dipendenze Python necessarie.
- `fatture_v3.db`: Database SQLite locale (creato automaticamente al primo avvio) contenente i dati estratti dalle fatture.
- `recover.py`: Script di recupero download falliti a partire da un JSON locale.
- `Dockerfile` / `docker-compose.yml`: File per l'esecuzione del servizio tramite Docker (opzionale!).
- `entrypoint.sh`: Script di gestione loop per esecuzione continua in container.

## Accessi e Gestione

L'applicazione utilizza un file di configurazione (default `.env`) per gestire:
- **Credenziali AdE**: Codice Fiscale, PIN e Password per l'accesso al portale "Fatture e Corrispettivi".
- **Parametri Operativi**: Partita IVA di destinazione, range temporale (`DATA_DAL`, `DATA_AL`), tipo di utenza, attivazione/disattivazione database e gestione scrittura locale (`WRITE`).

Il database SQLite (`fatture_v3.db`) viene inizializzato automaticamente e contiene tabelle dettagliate per anagrafiche, dati generali, righe di dettaglio, pagamenti, DDT e riferimenti a ordini/contratti.

## Tipologia e formato input

- **Configurazione**: File di testo in formato `.env` (chiave=valore), sia come profilo singolo `.env` sia come profili multipli in `aziende/.env.nomeprofilo`.
- **Argomenti CLI**: È possibile passare un profilo specifico come argomento (es. `python main.py azienda1` caricherà `aziende/.env.azienda1`) oppure usare `python main.py all` per forzare l'esecuzione batch di tutti i profili presenti in `aziende/`.
- **Interazione**: Se non specificato nel file `.env`, l'app richiederà interattivamente il tipo di utenza (Me Stesso, Delega Diretta, Incaricato).

## Tipologia e formato output

L'output viene generato nella cartella `output/{PIVA}_FE/`, suddivisa in:
- `RICEVUTE/` ed `EMESSE/`:
    - `ORIGINALI/`: Contiene i file originali scaricati dal portale (XML o P7M).
    - `INFO/`: Contiene i metadati e le informazioni associate fornite dall'AdE.
    - `FATTURE/`: Contiene esclusivamente i file in formato XML (estratti se originariamente P7M).
- **Database**: Dati strutturati salvati in `fatture_v3.db`.
- **JSON ricerca fatture**: In `output/JSON_extr/` vengono salvati i JSON completi delle fatture emesse/ricevute con timestamp.
- **Download pendenti**: In `output/JSON_extr/` viene mantenuto il file `download_failures_<PIVA>.json`, con sezioni separate `RICEVUTE` ed `EMESSE`. I pendenti vengono ritentati automaticamente nei run successivi e rimossi dal file non appena il download va a buon fine.
- **Log**: Il profilo `.env` usa `log_esecuzione.txt` e `log_recover.txt`; i profili in `aziende/` usano file dedicati in `output/logs/` (`log_<profilo>.txt` e `log_recover_<profilo>.txt`).
- **Modalita' WRITE=0**: Al termine del run viene rimossa la cartella `output/{PIVA}_FE`, mentre restano disponibili i JSON in `output/JSON_extr/`.

## Funzionalità aggiuntive

- **Estrazione P7M**: Conversione automatica dei file firmati in XML leggibile.
- **Supporto Multi-Database**: Supporta sia **SQLite** (file locale) che **MySQL** per il salvataggio dei dati.
- **Supporto Docker**: Configurazione pronta per avviare il tool come servizio continuo o on-demand.
- **Supporto Multi-Profilo**: Se la cartella `aziende/` contiene profili validi, `python main.py` li esegue automaticamente in serie; se un profilo fallisce, i successivi continuano.
- **Modalità Daily**: Configurando `DAILY=1`, l'app imposta automaticamente il range di ricerca tra ieri e oggi.
- **Gestione Chunk**: La ricerca viene suddivisa automaticamente in periodi di 3 mesi per superare i limiti temporali del portale AdE.
- **Deep Parsing**: Non solo download, ma estrazione di ogni dettaglio della fattura (incluse righe articolo e scadenze pagamenti).
- **Data Ricezione**: Per le ricevute viene salvata `dataConsegna`; per le emesse è impostata uguale alla data fattura.
- **Compatibilita' nuovo layout AdE**: Il flusso di autenticazione e instradamento e' allineato al nuovo layout del portale "Fatture e Corrispettivi".
- **Retry automatico**: I download che rispondono `304` o `503` vengono ritentati fino a 3 volte con backoff. Se restano pendenti, vengono accodati nel file `download_failures_<PIVA>.json` e ritentati automaticamente ai run successivi.
- **Recovery**: Possibilità di riprovare i download falliti leggendo un JSON locale.

## Istruzioni sommarie

1. Configura il file `.env` oppure crea uno o più profili dentro `aziende/`.
2. Installa le dipendenze: `pip install -r requirements.txt`.
3. Avvia lo script: `python main.py`.
4. Controlla la cartella dei risultati e il database per i dati estratti.

Se esiste la cartella `aziende/` con file come `.env.azienda1`, `.env.azienda2`, `python main.py` esegue automaticamente tutti i profili. Per un solo profilo puoi usare `python main.py azienda1`.
Se vuoi forzare il profilo principale `.env` anche quando esiste `aziende/`, usa `python main.py .env`.

Se si vuole automatizzare la procedura in modo tale che venga eseguita ogni giorno, leggi il paragrafo "Automatizza lo script" nel file `ISTRUZIONI.md`.

## Recupero download falliti

Usa `recover.py` passando il file pendenti della P.IVA oppure un vecchio JSON storico di fallimenti:

```bash
python recover.py output/JSON_extr/download_failures_<PIVA>.json
```

È possibile usare un file `.env` alternativo o un profilo dentro `aziende/`:

```bash
python recover.py output/JSON_extr/download_failures_<PIVA>.json --env azienda1
```
