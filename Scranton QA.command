#!/bin/zsh
# Scranton QA launcher - double-click me in Finder.
#
# Boots a THROWAWAY test environment: an isolated database and vector
# store under data/qa/, reseeded with the Dunder Mifflin demo dataset
# at every launch. The real data (data/scranton.db, data/chroma) is
# never touched, so the owner can test without any precaution.
#
# The interactive checklist opens at http://localhost:8010/qa.html and
# the app under test at http://localhost:8010. Closing this window (or
# Ctrl+C) stops the QA server. Set QA_NO_OPEN=1 to skip the browser
# (used by automated verification).

set -e
cd "$(dirname "$0")"

PORT=8010
QA_DIR="$PWD/data/qa"

# Everything physical comes from the environment (config.py seam):
# pointing these two variables at data/qa/ is the whole isolation.
export DATABASE_URL="sqlite:///$QA_DIR/scranton-qa.db"
export CHROMA_DIR="$QA_DIR/chroma"

echo "==============================================="
echo " Scranton QA - environnement de test jetable"
echo " (vos données réelles ne sont PAS touchées)"
echo "==============================================="

# A previous QA session may still hold the port: stop it quietly.
lsof -ti tcp:$PORT | xargs kill 2>/dev/null || true
sleep 1

rm -rf "$QA_DIR"
mkdir -p "$QA_DIR"

source .venv/bin/activate

# Same arm64 forcing as Scranton.app: the framework Python is universal
# and would follow a Rosetta terminal into x86_64, where the arm64
# wheels of the venv cannot load.
echo ""
echo "1/2 Semis du jeu de démo Dunder Mifflin (quelques secondes)..."
/usr/bin/arch -arm64 .venv/bin/python -m backend.app.db.seed --reset

echo ""
echo "2/2 Démarrage du serveur QA sur le port $PORT..."
echo ""
echo "   Checklist : http://localhost:$PORT/qa.html"
echo "   App       : http://localhost:$PORT"
echo ""
echo "   FERMEZ CETTE FENÊTRE (ou Ctrl+C) POUR ARRÊTER LE TEST."
echo ""

if [ -z "$QA_NO_OPEN" ]; then
  ( sleep 2; open "http://localhost:$PORT/qa.html" ) &
fi

exec /usr/bin/arch -arm64 .venv/bin/python -m uvicorn backend.app.main:app --port $PORT
