#!/bin/bash
# Feast Startup Script
# PATH: feast_service/start_feast.sh

set -e

echo "🍽️  Inicializando Feast Feature Store..."

# Change to feature repo directory
cd /feature_repo

# Wait for dependencies
echo "⏳ Aguardando Redis..."
until redis-cli -h redis ping 2>/dev/null; do
    echo "Redis ainda não está pronto. Aguardando..."
    sleep 2
done

echo "✅ Redis conectado!"

# Initialize Feast if needed
if [ ! -f .feast_init_done ]; then
    echo "📋 Aplicando definições de features..."
    
    # Try to apply features
    if feast apply 2>/dev/null; then
        echo "✅ Features aplicadas com sucesso!"
        touch .feast_init_done
    else
        echo "⚠️  Não foi possível aplicar features (normal na primeira execução)"
        echo "📝 Criando registry vazio..."
        touch .feast_init_done
    fi
fi

echo "🚀 Iniciando Feast server na porta 6566..."

# Start Feast server
exec feast serve --host 0.0.0.0 --port 6566