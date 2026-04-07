#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# PersonDB — Deploy Script
# Usage:
#   ./deploy.sh dev        — Local dev server (SQLite)
#   ./deploy.sh docker     — Full Docker stack (PostgreSQL + Nginx)
#   ./deploy.sh migrate    — Run migrations only
#   ./deploy.sh createsuperuser — Create admin user
#   ./deploy.sh export     — Export data to JSON
#   ./deploy.sh stop       — Stop Docker stack
# ============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[PersonDB]${NC} $1"; }
ok()    { echo -e "${GREEN}[  OK  ]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ── Ensure .env exists ──
ensure_env() {
  if [ ! -f .env ]; then
    info "Creating .env from .env.example..."
    cp .env.example .env
    # Generate random secret key
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || echo "dev-change-me-$(date +%s)")
    sed -i "s|change-me-to-random-50-char-string|${SECRET}|" .env
    ok ".env created — review and customize it!"
  fi
}

# ── Dev mode (SQLite, runserver) ──
cmd_dev() {
  info "Starting development server (SQLite)..."
  
  if ! command -v python3 &>/dev/null; then
    err "Python 3 not found. Install it first."
    exit 1
  fi

  # Virtual environment
  if [ ! -d "venv" ]; then
    info "Creating virtual environment..."
    python3 -m venv venv
  fi
  source venv/bin/activate

  info "Installing dependencies..."
  pip install -q -r requirements.txt

  mkdir -p db media/photos media/documents

  info "Creating migrations..."
  python manage.py makemigrations core --noinput

  info "Running migrations..."
  python manage.py migrate --noinput

  info "Collecting static files..."
  python manage.py collectstatic --noinput 2>/dev/null || true

  ok "Development server starting at http://localhost:8000"
  echo ""
  echo -e "  ${GREEN}╔══════════════════════════════════════╗${NC}"
  echo -e "  ${GREEN}║  PersonDB running on :8000           ║${NC}"
  echo -e "  ${GREEN}║  Theme: \${PERSONDB_THEME:-matrix}             ║${NC}"
  echo -e "  ${GREEN}║  DB: SQLite                          ║${NC}"
  echo -e "  ${GREEN}║  Ctrl+C to stop                      ║${NC}"
  echo -e "  ${GREEN}╚══════════════════════════════════════╝${NC}"
  echo ""

  python manage.py runserver 0.0.0.0:8000
}

# ── Docker mode ──
cmd_docker() {
  ensure_env
  info "Building and starting Docker stack..."

  if ! command -v docker &>/dev/null; then
    err "Docker not found. Install Docker first."
    exit 1
  fi

  docker compose build
  docker compose up -d

  info "Waiting for database..."
  sleep 5

  docker compose exec web python manage.py makemigrations core --noinput
  docker compose exec web python manage.py migrate --noinput
  docker compose exec web python manage.py collectstatic --noinput

  APP_PORT=$(grep APP_PORT .env 2>/dev/null | cut -d= -f2 || echo "8000")
  NGINX_PORT=$(grep NGINX_PORT .env 2>/dev/null | cut -d= -f2 || echo "80")

  ok "Docker stack is running!"
  echo ""
  echo -e "  ${GREEN}╔══════════════════════════════════════╗${NC}"
  echo -e "  ${GREEN}║  PersonDB Docker Stack               ║${NC}"
  echo -e "  ${GREEN}║  App:   http://localhost:${APP_PORT:-8000}        ║${NC}"
  echo -e "  ${GREEN}║  Nginx: http://localhost:${NGINX_PORT:-80}          ║${NC}"
  echo -e "  ${GREEN}║  DB:    PostgreSQL :5432              ║${NC}"
  echo -e "  ${GREEN}╚══════════════════════════════════════╝${NC}"
  echo ""
  echo "  Run: ./deploy.sh createsuperuser"
}

# ── Migrate ──
cmd_migrate() {
  if [ -f "docker-compose.yml" ] && docker compose ps --status running 2>/dev/null | grep -q web; then
    docker compose exec web python manage.py makemigrations core --noinput
    docker compose exec web python manage.py migrate --noinput
  else
    source venv/bin/activate 2>/dev/null || true
    python manage.py makemigrations core --noinput
    python manage.py migrate --noinput
  fi
  ok "Migrations complete."
}

# ── Create superuser ──
cmd_createsuperuser() {
  if docker compose ps --status running 2>/dev/null | grep -q web; then
    docker compose exec -it web python manage.py createsuperuser
  else
    source venv/bin/activate 2>/dev/null || true
    python manage.py createsuperuser
  fi
}

# ── Export ──
cmd_export() {
  info "Exporting data..."
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  OUTFILE="data/json/persondb_export_${TIMESTAMP}.json"
  mkdir -p data/json
  if docker compose ps --status running 2>/dev/null | grep -q web; then
    docker compose exec web python manage.py dumpdata core --indent 2 > "$OUTFILE"
  else
    source venv/bin/activate 2>/dev/null || true
    python manage.py dumpdata core --indent 2 > "$OUTFILE"
  fi
  ok "Exported to ${OUTFILE}"
}

# ── Stop ──
cmd_stop() {
  info "Stopping Docker stack..."
  docker compose down
  ok "Stopped."
}

# ── Main ──
case "${1:-dev}" in
  dev)             cmd_dev ;;
  docker)          cmd_docker ;;
  migrate)         cmd_migrate ;;
  createsuperuser) cmd_createsuperuser ;;
  export)          cmd_export ;;
  stop)            cmd_stop ;;
  *)
    echo "Usage: $0 {dev|docker|migrate|createsuperuser|export|stop}"
    exit 1 ;;
esac
