#!/bin/bash
#
# JARVIS Web UI - Startup Script
# Usage: ./run.sh [port]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PORT="${1:-5000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           J.A.R.V.I.S. WEB SERVER STARTUP                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python
echo -e "${YELLOW}[CHECK] Python availability...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 not found${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}[OK] $PYTHON_VERSION${NC}"

# Check environment
echo -e "${YELLOW}[CHECK] API keys in environment...${NC}"
if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${YELLOW}[WARN] GEMINI_API_KEY not set (will prompt on web UI)${NC}"
else
    echo -e "${GREEN}[OK] GEMINI_API_KEY set${NC}"
fi

if [ -z "$OPENROUTER_API_KEY" ]; then
    echo -e "${YELLOW}[WARN] OPENROUTER_API_KEY not set (will prompt on web UI)${NC}"
else
    echo -e "${GREEN}[OK] OPENROUTER_API_KEY set${NC}"
fi

# Install dependencies
echo -e "${YELLOW}[INSTALL] Python dependencies...${NC}"
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

source "$SCRIPT_DIR/.venv/bin/activate"

if [ -f "$SCRIPT_DIR/requirements_web.txt" ]; then
    pip install -q -r "$SCRIPT_DIR/requirements_web.txt"
    echo -e "${GREEN}[OK] Dependencies installed${NC}"
else
    echo -e "${YELLOW}[WARN] requirements_web.txt not found${NC}"
fi

# Install parent repo dependencies (for backend integration)
if [ -f "$REPO_ROOT/requirements.txt" ]; then
    echo -e "${YELLOW}[INSTALL] Parent repo dependencies...${NC}"
    pip install -q -r "$REPO_ROOT/requirements.txt" || true
    echo -e "${GREEN}[OK] Parent dependencies installed${NC}"
fi

# Start server
echo -e "${YELLOW}[START] Starting JARVIS web server...${NC}"
echo -e "${GREEN}"
echo "🌐 Web UI: http://localhost:${PORT}"
echo "📡 WebSocket: ws://localhost:${PORT}/socket.io"
echo "📊 API: http://localhost:${PORT}/api"
echo -e "${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

export PYTHONUNBUFFERED=1
export FLASK_ENV=development

cd "$SCRIPT_DIR"
python3 app.py
