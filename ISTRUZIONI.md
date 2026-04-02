# Istruzioni di Funzionamento - FE Scraper

Questa guida spiega come installare, configurare e utilizzare l'applicazione FE Scraper per il download e il parsing automatico delle fatture elettroniche.

## 1. Installazione

### Requisiti preliminari
- Python 3.8 o superiore installato sul sistema.
- Connessione a internet attiva.

### Procedura
1. Scarica o clona il repository sul tuo computer.
2. Apri un terminale (o prompt dei comandi) nella cartella del progetto.
3. Installa le librerie necessarie eseguendo il comando:
   ```bash
   pip install -r requirements.txt
   ```

## 2. Configurazione

### Il file .env
Crea o modifica il file `.env` nella cartella principale. Questo file deve contenere i seguenti parametri:

```env
# Credenziali Agenzia Entrate
CF=IlTuoCodiceFiscale
PIN=IlTuoPin
PASSWORD=LaTuaPassword

# Azienda target (obbligatoria se non si usa "Me Stesso")
PIVA=01234567890

# Range date (formato GG/MM/AAAA)
DATA_DAL=01/01/2024
DATA_AL=31/12/2024

# Impostazioni opzionali
UTENZA=1
# 1: Me stesso, 2: Delega Diretta, 3: Incaricato
TIPO=FOL        
# Tipo di accesso per intermediari (FOL/ENT) obbligatorio se UTENZA=3
DAILY=0         
# 1 per scaricare solo le fatture di ieri/oggi
DB=1            
# 1 per salvare i dati nel database, 0 per solo download file
WRITE=1
# 1 per mantenere i file scaricati su disco, 0 per rimuovere a fine run la cartella output/{PIVA}_FE

# --- CONFIGURAZIONE DATABASE ---
DB_TYPE=sqlite
# Valori ammessi: sqlite, mysql

# Parametri per SQLite
DB_SQLITE_PATH=fatture_v3.db

# Parametri per MySQL (usati solo se DB_TYPE=mysql)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=fatture_db
DB_USER=root
DB_PASS=
```

**Nota bene**: Se desideri gestire più clienti, il metodo consigliato è creare una cartella `aziende/` e inserirvi file come `.env.cliente1`, `.env.cliente2`, `.env.cliente3`.

## 3. Avvio dell'applicazione

### Esecuzione standard
Per avviare il processo utilizzando il file `.env` predefinito:
```bash
python main.py
```

Se nella cartella principale esiste `aziende/` e contiene profili validi, lo stesso comando `python main.py` esegue automaticamente tutti i profili presenti in serie.
Questa modalità batch ha precedenza sul profilo `.env`. Se vuoi forzare l'uso del solo `.env`, esegui:
```bash
python main.py .env
```

### Esecuzione con profilo specifico
Se hai creato un file di configurazione chiamato `aziende/.env.mario_rossi`, puoi caricarlo passando il nome come argomento:
```bash
python main.py mario_rossi
```

### Esecuzione batch esplicita
Se vuoi forzare l'esecuzione di tutti i profili presenti in `aziende/`, puoi usare:
```bash
python main.py all
```

### Struttura consigliata per i multi-profili

```text
FE-Scraper-AdE/
├── aziende/
│   ├── .env.azienda1
│   ├── .env.azienda2
│   └── .env.azienda3
├── output/
└── main.py
```

Ogni file dentro `aziende/` deve contenere una configurazione completa e autonoma. In particolare:
- `UTENZA` deve essere sempre valorizzato, per evitare richieste interattive durante il batch.
- Se `UTENZA != 1`, anche `PIVA` deve essere valorizzata.
- È consigliato mantenere `DAILY=1` se vuoi un ciclo giornaliero automatico per tutti i clienti.

## 4. Flusso di lavoro

1. **Autenticazione**: Lo script accede al portale "Fatture e Corrispettivi" dell'Agenzia delle Entrate tramite il nuovo flusso IAMPE/portale.
2. **Selezione Utenza**: L'app seleziona il tipo di delega o l'accesso diretto (`ME_STESSO`, `DELEGA_DIRETTA`, `INTERMEDIARIO`).
3. **Ricerca**: Vengono cercate le fatture emesse e ricevute nel periodo indicato. La ricerca è suddivisa in blocchi trimestrali automatici.
4. **Download**: I file vengono scaricati e salvati nella cartella `output/{PIVA}_FE`.
5. **Retry pendenti**: Al termine del download giornaliero, il sistema controlla se esiste `output/JSON_extr/download_failures_<PIVA>.json` e prova automaticamente a riscaricare le fatture ancora pendenti.
6. **Estrazione e Parsing**:
   - I file `.p7m` vengono decifrati in `.xml`.
   - I contenuti degli XML vengono letti e salvati nel database `fatture_v3.db`.
7. **Report**: Al termine, viene visualizzato un riepilogo a video e salvato un file log dedicato al profilo.

### Log per profilo

- Profilo singolo `.env`: `log_esecuzione.txt`
- Recover su `.env`: `log_recover.txt`
- Profilo `aziende/.env.azienda1`: `output/logs/log_azienda1.txt`
- Recover su `aziende/.env.azienda1`: `output/logs/log_recover_azienda1.txt`

I log vengono mantenuti in append: ogni nuovo ciclo aggiunge le nuove righe allo stesso file del profilo, senza crearne uno nuovo ogni volta.

## 5. JSON di ricerca fatture

Durante l'esecuzione, lo script salva una copia completa delle risposte di ricerca:
- `output/JSON_extr/fatture_ricevute_YYYYMMDD_HHMMSS.json`
- `output/JSON_extr/fatture_emesse_YYYYMMDD_HHMMSS.json`

Questi file contengono tutti i campi restituiti dall'API, utili per individuare dati aggiuntivi da integrare nel DB.
Possono essere cancellati se non servono.

Se `WRITE=0`, la cartella `output/{PIVA}_FE` viene rimossa a fine esecuzione, mentre `output/JSON_extr/` resta disponibile.

## 6. Data Ricezione in DB (rev1)

È stata introdotta la colonna `data_ricezione` nella tabella `dati_generali`:
- Per fatture **ricevute**: viene usato il campo `dataConsegna` del JSON di ricerca.
- Per fatture **emesse**: `data_ricezione` viene impostata uguale alla `data` della fattura (dal file XML).

### Migrazione automatica

Se il DB esiste già, all'avvio viene eseguito un controllo e, se manca la colonna, viene applicato:
```sql
ALTER TABLE dati_generali ADD COLUMN data_ricezione TEXT
```

## 7. Gestione download falliti

Quando un download di `FILE_FATTURA` fallisce, il sistema aggiorna il file:

- `output/JSON_extr/download_failures_<PIVA>.json`

Il file contiene un backlog persistente per quella P.IVA, con due sezioni:
- `categories.RICEVUTE`
- `categories.EMESSE`

Ogni voce contiene almeno `idFattura`, `tipoInvio`, `status`, `url`, `category`, `tipoFile`, oltre ai metadati di tracking (`first_seen`, `last_seen`, `attempts`) quando il fallimento nasce durante un run di `main.py`.

In caso di errore, il log riporta anche i parametri completi usati per il download.

### Retry automatico

Per status `304` e `503` viene eseguito automaticamente un retry immediato fino a 3 tentativi con backoff.

Se anche dopo i 3 tentativi il file non e' disponibile, la fattura resta nel file `download_failures_<PIVA>.json` e verra' ritentata automaticamente nei run successivi.

## 8. Recovery download

Per riprovare i download falliti senza rifare la ricerca sul portale, usa `recover.py`:

```bash
python recover.py output/JSON_extr/download_failures_<PIVA>.json
```

#### Con profilo `.env` alternativo

```bash
python recover.py output/JSON_extr/download_failures_<PIVA>.json --env .profilo
```

Il recovery usa le stesse credenziali del profilo e scarica solo le fatture indicate nel JSON locale.
Puoi anche usare direttamente un profilo in `aziende/`, ad esempio:

```bash
python recover.py output/JSON_extr/download_failures_<PIVA>.json --env azienda1
```

E' compatibile anche con i vecchi file JSON storici di fallimento generati nelle versioni precedenti.

## 9. Automatizza lo script (Windows Task Scheduler)

Questa procedura consente di eseguire lo script ogni giorno in modo automatico.

### Prerequisiti

1. Verifica di poter eseguire manualmente `python main.py` senza errori.
2. Assicurati che il file `.env` oppure tutti i profili in `aziende/` siano configurati correttamente e che, se vuoi l'esecuzione giornaliera automatica, `DAILY=1`.
3. Individua il percorso completo di Python e della cartella del progetto.

### Passi operativi

1. Apri "Utilità di pianificazione" (Task Scheduler).
2. Clicca "Crea attività di base".
3. Dai un nome all'attività, ad esempio `FE Scraper Daily`.
4. Scegli "Giornaliera" come trigger e imposta ora di esecuzione.
5. Seleziona "Avvia un programma".
6. Compila i campi come segue:
7. Programma/script: percorso di Python, ad esempio `C:\Python311\python.exe`.
8. Aggiungi argomenti: `main.py`
9. Avvia in: percorso della cartella del progetto, ad esempio `C:\progetti\FE-Scraper-AdE`
10. Conferma e termina la procedura.

### Verifica

1. Esegui l'attività manualmente con "Esegui".
2. Controlla il file log del profilo (`log_esecuzione.txt` oppure `output/logs/log_<profilo>.txt`) e la cartella `output/{PIVA}_FE` per verificare l'output. Se `WRITE=0`, controlla `output/JSON_extr/`.

### Note utili

1. Se usi i multi-profili, ti basta mettere i file in `aziende/`: `python main.py` li esegue tutti in automatico. Per un profilo singolo usa `main.py profilo` (es. `main.py mario_rossi`).
2. Se il task non parte, controlla i log di Windows e verifica che il percorso di Python sia corretto.

## 10. Risoluzione dei problemi

- **Errore di login o token B2B**: Solitamente dovuto a credenziali errate, sessione non valida o portale dell'Agenzia delle Entrate momentaneamente non disponibile.
- **Dipendenze mancanti**: Assicurati di aver eseguito correttamente `pip install -r requirements.txt`.
- **Database bloccato**: Se apri il file `fatture_v3.db` con un software esterno durante l'esecuzione, lo script potrebbe fallire il salvataggio dei dati.
- **Errore "Codice utenza non valido"**: Evita commenti inline nella riga `UTENZA` del file `.env`.
- **Status 304 sul download**: Il portale potrebbe non avere ancora reso disponibile il file. In questo caso il sistema ritenta automaticamente e, se necessario, accoda la fattura nel file `download_failures_<PIVA>.json`.

---

## 11. Supporto Multi-Database (SQLite / MySQL)

È possibile scegliere dove salvare le fatture scaricate:
1.  **SQLite** (Predefinito): Nessuna configurazione richiesta, crea un file `.db` locale.
2.  **MySQL**: Richiede l'installazione di una libreria aggiuntiva e la configurazione delle variabili nel file `.env`.

### Utilizzo con MySQL
1.  **Installa il driver**:
    ```bash
    pip install pymysql
    ```
2.  **Configura `.env`**:
    *   Imposta `DB_TYPE=mysql`
    *   Compila i campi `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASS`.

---

## 12. Esecuzione tramite Docker

È possibile eseguire l'applicazione all'interno di un container Docker, sia come servizio continuo che on-demand.

### Prerequisiti
*   Docker e Docker Compose installati sul sistema.

### Configurazione
1.  **File `.env`**: Assicurati di aver configurato il tuo file `.env` nella cartella principale.
    Se vuoi eseguire più aziende in Docker, crea invece la cartella `aziende/` con i profili `.env.nomeprofilo`.
2.  **Modalità Servizio (Loop)**:
    Nel file `docker-compose.yml`, puoi configurare:
    ```yaml
    environment:
      - DOCKER_LOOP=1  # 1 per ciclo continuo, 0 per run singolo
      - LOOP_SLEEP=86400  # Tempo in secondi tra i cicli (86400 = 24 ore)
    ```

### Avvio e Modalità di Esecuzione

Dato che il container interroga l'Agenzia delle Entrate ad ogni avvio (filtrando se `DAILY=1`), hai due modi per farlo girare:

Se monti `./aziende:/app/aziende:ro`, il comando `python main.py` dentro al container esegue automaticamente tutti i profili presenti in `aziende/`.

#### **A) Esecuzione Singola "On-Demand" (Consigliata per lanci manuali)**
Ideale se vuoi lanciarlo tu quando serve, vedere l'output davanti a te e farlo spegnere da solo alla fine senza spreco di risorse.
```bash
docker compose run --rm scraper
```
*Questo comando crea un container temporaneo, esegue lo scaricamento e lo elimina alla fine, preservando i file.*

#### **B) Esecuzione "Sempre Attivo" (Ciclo continuo)**
Se nel `docker-compose.yml` hai impostato `DOCKER_LOOP=1`, il servizio rimarrà sempre in background:
```bash
# Avvio iniziale (in background)
docker compose up -d

# Riavvio istantaneo (per forzare un ciclo)
docker compose restart scraper
```

---

### 📂 Gestione dei Duplicati
Non c'è rischio di sovrascrivere o raddoppiare i dati: se un file o una fattura scaricata è già presente nel database, lo script la salta (`[DB] Salto (già presente)`).

### Rete (Network)
Il file `docker-compose.yml` è configurato per agganciarsi alla rete `shared-internal-net`:
```yaml
networks:
  fescraper-net:
    external: true
    name: shared-internal-net
```
Assicurati che la rete sia già attiva (es. creata con `docker network create shared-internal-net`) per evitare errori durante l'avvio, soprattutto se necessaria per raggiungere un database MySQL esterno. Se hai già un database MySQL, assicurati che sia collegato alla stessa rete.

esempio docker-compose.yml per MySQL e PHPMyAdmin:
```yaml
services:
  # IL TUO DATABASE
  db:
    image: mysql:8.0
    container_name: mysql_server
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: METTI-UNA-PASSWORD-SICURA
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - backend_net

  # L'INTERFACCIA DI GESTIONE
  phpmyadmin:
    image: phpmyadmin/phpmyadmin
    container_name: pma
    restart: always
    environment:
      PMA_HOST: db
    ports:
      - "8080:80"
    depends_on:
      - db
    networks:
      - backend_net

volumes:
  mysql_data:

networks:
  backend_net:
        external: true
        name: shared-internal-net
```
