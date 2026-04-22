#!/bin/bash
set -e

# ── Vérifie / installe Docker ─────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "Docker non trouvé, installation en cours..."
    if command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm docker docker-compose
    elif command -v apt-get &>/dev/null; then
        sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y docker docker-compose-plugin
    elif command -v brew &>/dev/null; then
        brew install --cask docker
        echo "Lance Docker Desktop puis relance ce script."
        exit 0
    else
        echo "Impossible d'installer Docker automatiquement."
        echo "Installe Docker manuellement : https://docs.docker.com/get-docker/"
        exit 1
    fi
fi

# ── Démarre le daemon Docker si nécessaire (Linux) ────────────────────────────
if ! docker info &>/dev/null 2>&1; then
    echo "Démarrage du daemon Docker..."
    sudo systemctl start docker
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    sleep 3
    if ! docker info &>/dev/null 2>&1; then
        echo "Impossible de démarrer Docker. Lance-le manuellement."
        exit 1
    fi
fi

# ── Lance l'application ───────────────────────────────────────────────────────
cd "$(dirname "$0")"

# Construit l'image si elle n'existe pas encore
if ! docker image inspect mtg_biblio-app &>/dev/null 2>&1; then
    echo "Première exécution — construction de l'image (quelques minutes)..."
    docker compose build
fi

docker compose up -d
echo ""
echo "MTG Collection lancé → http://localhost:8090"
