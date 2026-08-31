#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
# Seismic Viewer Thesis - LaTeX Compilation Script
# Run this script from WSL: bash compile.sh
# ══════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════════════════════"
echo "  Seismic Viewer Thesis - LaTeX Compilation"
echo "═══════════════════════════════════════════════════════"

# Check for pdflatex
if ! command -v pdflatex &> /dev/null; then
    echo ""
    echo "[!] pdflatex not found. Installing texlive..."
    echo ""
    sudo apt-get update -qq
    sudo apt-get install -y -qq texlive-full
    echo ""
    echo "[✓] texlive installed successfully."
fi

# Check for bibtex
if ! command -v bibtex &> /dev/null; then
    echo "[!] bibtex not found. It should have been installed with texlive."
    exit 1
fi

echo ""
echo "[1/4] First pdflatex pass..."
pdflatex -interaction=nonstopmode -halt-on-error main.tex

echo ""
echo "[2/4] Running bibtex..."
bibtex main || echo "[!] bibtex warnings (non-fatal)"

echo ""
echo "[3/4] Second pdflatex pass..."
pdflatex -interaction=nonstopmode -halt-on-error main.tex

echo ""
echo "[4/4] Third pdflatex pass (final)..."
pdflatex -interaction=nonstopmode -halt-on-error main.tex

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  [✓] Compilation complete!"
echo "  Output: $(pwd)/main.pdf"
echo "═══════════════════════════════════════════════════════"

# Page count
if command -v pdfinfo &> /dev/null; then
    PAGES=$(pdfinfo main.pdf 2>/dev/null | grep "Pages:" | awk '{print $2}')
    echo "  Pages: $PAGES"
elif command -v pdftotext &> /dev/null; then
    echo "  (Install poppler-utils for page count)"
fi

echo ""
