FROM python:3.11-slim

# Installa dipendenze di sistema (opzionali ma utili per compilazione ed estrazione)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia e installa requisiti
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il resto dell'applicazione
COPY . .

# Rende eseguibile l'entrypoint
RUN chmod +x entrypoint.sh

# Entrypoint per gestire loop continuo o run singolo
ENTRYPOINT ["./entrypoint.sh"]
