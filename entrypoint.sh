#!/bin/bash

# Se la variabile d'ambiente DOCKER_LOOP è impostata a 1, esegue in ciclo
if [ "$DOCKER_LOOP" = "1" ]; then
    echo "[DOCKER] Modalità Loop continua attivata."
    # LOOP_SLEEP default: 24 ore (86400 secondi)
    SLEEP_TIME=${LOOP_SLEEP:-86400}
    
    while true; do
        echo "[DOCKER] --- Avvio ciclo di scaricamento ---"
        python main.py
        echo "[DOCKER] --- Esecuzione terminata. Prossimo avvio tra $SLEEP_TIME secondi ---"
        sleep $SLEEP_TIME
    done
else
    # Esecuzione singola standard
    exec python main.py "$@"
fi
