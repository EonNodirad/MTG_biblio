#!/bin/bash
set -e

# Génère un certificat SSL auto-signé au premier démarrage
SSL_DIR=/app/ssl
mkdir -p "$SSL_DIR"

if [ ! -f "$SSL_DIR/cert.pem" ]; then
    echo "Génération du certificat SSL auto-signé..."
    openssl req -x509 -newkey rsa:2048 \
        -keyout "$SSL_DIR/key.pem" \
        -out    "$SSL_DIR/cert.pem" \
        -days 3650 -nodes \
        -subj "/CN=mtg-collection-local" \
        2>/dev/null
    echo "Certificat prêt."
fi

exec uvicorn main:app \
    --host 0.0.0.0 --port 8000 \
    --ssl-keyfile "$SSL_DIR/key.pem" \
    --ssl-certfile "$SSL_DIR/cert.pem"
