#!/bin/bash
# setup_airflow.sh - Configuração rápida do Airflow

echo "🚀 Configurando Airflow no Pipeline de Dados..."

# 1. Criar estrutura de pastas
echo "📁 Criando pastas..."
mkdir -p airflow/{dags,logs,plugins}

# 2. Configurar permissões
echo "🔐 Configurando permissões..."
sudo chown -R 1000:1000 airflow/

# 3. Verificar se .env existe
if [ ! -f .env ]; then
    echo "❌ Arquivo .env não encontrado!"
    echo "Crie o arquivo .env com as configurações do Airflow"
    exit 1
fi

# 4. Gerar chave Fernet se necessário
if ! grep -q "AIRFLOW__CORE__FERNET_KEY=" .env || grep -q "YourFernetKeyHere" .env; then
    echo "🔑 Gerando chave Fernet..."
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    sed -i "s/YourFernetKeyHere/$FERNET_KEY/" .env
    echo "✅ Chave Fernet configurada"
fi

# 5. Iniciar banco do Airflow
echo "🗄️  Iniciando banco do Airflow..."
docker compose up -d airflow-db

# 6. Aguardar banco ficar pronto
echo "⏳ Aguardando banco ficar pronto..."
timeout 60 bash -c 'until docker compose exec -T airflow-db pg_isready -U airflow -d airflow -q; do sleep 2; done'

# 7. Executar inicialização
echo "🔄 Inicializando Airflow..."
docker compose up airflow-init

# 8. Iniciar serviços do Airflow
echo "▶️  Iniciando Airflow Webserver e Scheduler..."
docker compose up -d airflow-webserver airflow-scheduler

# 9. Aguardar Airflow ficar pronto
echo "⏳ Aguardando Airflow ficar pronto..."
timeout 120 bash -c 'until curl -f http://localhost:8081/health >/dev/null 2>&1; do sleep 5; done'

echo "✅ Airflow configurado com sucesso!"
echo ""
echo "🌐 Acesse: http://localhost:8081"
echo "👤 Usuário: admin"
echo "🔑 Senha: admin123"
echo ""
echo "🔍 Para verificar status: docker compose ps"
echo "📋 Para ver logs: docker compose logs airflow-webserver"