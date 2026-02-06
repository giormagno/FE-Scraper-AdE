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
# 1 per salvare i dati nel database SQLite, 0 per solo download file

```

**Nota bene**: Se desideri gestire più clienti, puoi creare file diversi come `.cliente1`, `.cliente2` e caricarli all'avvio (vedi sezione Avvio).

## 3. Avvio dell'applicazione

### Esecuzione standard
Per avviare il processo utilizzando il file `.env` predefinito:
```bash
python main.py
```

### Esecuzione con profilo specifico
Se hai creato un file di configurazione chiamato `.mario_rossi`, puoi caricarlo passando il nome come argomento:
```bash
python main.py mario_rossi
```

## 4. Flusso di lavoro

1. **Autenticazione**: Lo script accede al portale "Fatture e Corrispettivi" dell'Agenzia delle Entrate.
2. **Selezione Utenza**: L'app seleziona il tipo di delega o l'accesso diretto.
3. **Ricerca**: Vengono cercate le fatture emesse e ricevute nel periodo indicato. La ricerca è suddivisa in blocchi trimestrali automatici.
4. **Download**: I file vengono scaricati e salvati nella cartella `{PIVA}_FE`.
5. **Estrazione e Parsing**:
   - I file `.p7m` vengono decifrati in `.xml`.
   - I contenuti degli XML vengono letti e salvati nel database `fatture_v3.db`.
6. **Report**: Al termine, viene visualizzato un riepilogo a video e salvato un file `log_esecuzione.txt`.

## 6. JSON di ricerca fatture

Durante l'esecuzione, lo script salva una copia completa delle risposte di ricerca:
- `JSON_extr/fatture_ricevute_YYYYMMDD_HHMMSS.json`
- `JSON_extr/fatture_emesse_YYYYMMDD_HHMMSS.json`

Questi file contengono tutti i campi restituiti dall'API, utili per individuare dati aggiuntivi da integrare nel DB.
Possono essere cancellati se non servono.

## 7. Data Ricezione in DB (rev1)

È stata introdotta la colonna `data_ricezione` nella tabella `dati_generali`:
- Per fatture **ricevute**: viene usato il campo `dataConsegna` del JSON di ricerca.
- Per fatture **emesse**: `data_ricezione` viene impostata uguale alla `data` della fattura (dal file XML).

### Migrazione automatica

Se il DB esiste già, all'avvio viene eseguito un controllo e, se manca la colonna, viene applicato:
```sql
ALTER TABLE dati_generali ADD COLUMN data_ricezione TEXT
```

## 8. Gestione download falliti

Quando un download fallisce, vengono creati due file per categoria (in `{PIVA}_FE/RICEVUTE/` e `{PIVA}_FE/EMESSE/`):
- `download_failures.json`: elenco testuale degli errori.
- `download_failures_struct.json`: elenco strutturato con `idFattura`, `tipoInvio`, `status`, `url`, `category`.

In caso di errore, il log riporta anche i parametri completi usati per il download.

### Retry automatico

Per status 304 e 503 viene eseguito automaticamente un retry fino a 3 tentativi con backoff.

## 9. Recovery download

Per riprovare i download falliti senza rifare la ricerca sul portale, usa `recover.py`:

```bash
python recover.py /percorso/al/download_failures_struct.json
```

#### Con profilo `.env` alternativo

```bash
python recover.py /percorso/al/download_failures_struct.json --env .profilo
```

Il recovery usa le stesse credenziali del profilo e scarica solo le fatture indicate nel JSON locale.

## 10. Automatizza lo script (Windows Task Scheduler)

Questa procedura consente di eseguire lo script ogni giorno in modo automatico.

### Prerequisiti

1. Verifica di poter eseguire manualmente `python main.py` senza errori.
2. Assicurati che il file `.env` sia configurato e che, se vuoi l'esecuzione giornaliera automatica, `DAILY=1`.
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
2. Controlla `log_esecuzione.txt` e la cartella `{PIVA}_FE` per verificare l'output.

### Note utili

1. Se usi un profilo diverso dal `.env`, imposta l'argomento come `main.py profilo` (es. `main.py mario_rossi`).
2. Se il task non parte, controlla i log di Windows e verifica che il percorso di Python sia corretto.

## 5. Risoluzione dei problemi

- **Errore Liferay.authToken**: Solitamente dovuto a credenziali errate o portale dell'Agenzia delle Entrate momentaneamente non disponibile.
- **Dipendenze mancanti**: Assicurati di aver eseguito correttamente `pip install -r requirements.txt`.
- **Database bloccato**: Se apri il file `fatture_v3.db` con un software esterno durante l'esecuzione, lo script potrebbe fallire il salvataggio dei dati.
- **Errore "Codice utenza non valido"**: Evita commenti inline nella riga `UTENZA` del file `.env`.
