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
UTENZA=1        # 1: Me stesso, 2: Delega Diretta, 3: Incaricato
DAILY=0         # 1 per scaricare solo le fatture di ieri/oggi
DB=1            # 1 per salvare i dati nel database SQLite, 0 per solo download file
TIPO=FOL        # Tipo di accesso per intermediari (FOL/ENT)
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

## 5. Risoluzione dei problemi

- **Errore Liferay.authToken**: Solitamente dovuto a credenziali errate o portale dell'Agenzia delle Entrate momentaneamente non disponibile.
- **Dipendenze mancanti**: Assicurati di aver eseguito correttamente `pip install -r requirements.txt`.
- **Database bloccato**: Se apri il file `fatture_v3.db` con un software esterno durante l'esecuzione, lo script potrebbe fallire il salvataggio dei dati.
