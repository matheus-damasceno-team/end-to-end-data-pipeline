#!/bin/bash

echo "🔧 Instalando dependências para geração de diagramas..."

# Verificar se o graphviz está instalado
if ! command -v dot &> /dev/null; then
    echo "📦 Graphviz não encontrado. Instalando..."
    
    # Detectar sistema operacional
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y graphviz
        elif command -v yum &> /dev/null; then
            sudo yum install -y graphviz
        elif command -v pacman &> /dev/null; then
            sudo pacman -S graphviz
        else
            echo "❌ Gerenciador de pacotes não suportado. Instale graphviz manualmente."
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install graphviz
        else
            echo "❌ Homebrew não encontrado. Instale via: https://brew.sh/"
            exit 1
        fi
    else
        echo "❌ Sistema operacional não suportado. Instale graphviz manualmente."
        exit 1
    fi
else
    echo "✅ Graphviz já está instalado."
fi

# Instalar biblioteca diagrams
echo "📦 Instalando biblioteca diagrams..."
python3 -m pip install diagrams

echo "✅ Dependências instaladas com sucesso!"
echo "🚀 Agora você pode executar: python3 generate_architecture_diagrams.py"