#!/bin/sh
# bootstrap.sh - baixa o repositorio da NeoAI e instala TUDO de que ela
# precisa (Playwright + Chromium), de uma vez so.
#
# Uso (Linux / Termux / macOS):
#   curl -fsSL https://raw.githubusercontent.com/LEVIATAD21/NeoAI/main/bootstrap.sh | sh
# ou, ja dentro de uma pasta:
#   sh bootstrap.sh
#
# Na primeira vez vo so executa ESTE comando e pronto: repo baixado,
# dependencias instaladas.
set -e

AULA="\033[93m[aula] "
OK="\033[92m[ok] "
FIM="\033[0m"
REPO="https://github.com/LEVIATAD21/NeoAI.git"

echo "${AULA}Baixando o repositorio da NeoAI...${FIM}"
if [ ! -d NeoAI/.git ]; then
    git clone "$REPO" NeoAI
else
    echo "${OK}Repo NeoAI ja existe, atualizando...${FIM}"
    git -C NeoAI pull --ff-only
fi

cd NeoAI

echo "${AULA}Instalando tudo de que a NeoAI precisa...${FIM}"
if command -v python3 >/dev/null 2>&1; then
    python3 instala.py
elif command -v python >/dev/null 2>&1; then
    python instala.py
else
    echo "Python 3 nao encontrado. Instale primeiro:"
    echo "  Termux: pkg install python-pip"
    echo "  Debian/Ubuntu: apt install python3 python3-pip git"
    exit 1
fi

echo
echo "${OK}Pronto! Rode com:  python3 neoai.py${FIM}"