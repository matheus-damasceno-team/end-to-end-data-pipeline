#!/bin/bash

# Script para configurar dbt com Trino para camada Silver

echo "=== Configurando dbt com Trino para Iceberg ==="

# Criar estrutura de diretórios
echo "Criando estrutura de diretórios..."
mkdir -p dbt_iceberg/{models/{staging,silver,marts},macros,tests/{generic,singular},data,analyses,snapshots}
mkdir -p services/dbt-trino

# Copiar Dockerfile do dbt-trino
echo "Criando Dockerfile para dbt-trino..."
cat > services/dbt-trino/Dockerfile << 'EOF'
FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    dbt-core==1.7.0 \
    dbt-trino==1.7.0

WORKDIR /dbt
ENV DBT_PROFILES_DIR=/dbt

CMD ["dbt", "run"]
EOF

# Criar arquivo de configuração do dbt
echo "Criando arquivos de configuração..."

# Copiar arquivos para o diretório dbt_iceberg
cp dbt_project.yml dbt_iceberg/ 2>/dev/null || echo "dbt_project.yml será criado"
cp profiles.yml dbt_iceberg/ 2>/dev/null || echo "profiles.yml será criado"

# Criar packages.yml
cat > dbt_iceberg/packages.yml << 'EOF'
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
EOF

# Criar .gitignore
cat > dbt_iceberg/.gitignore << 'EOF'
target/
dbt_packages/
logs/
.DS_Store
*.log
.env
EOF

# Criar README específico
cat > dbt_iceberg/README.md << 'EOF'
# dbt Silver Layer com Trino e Iceberg

Este projeto implementa a camada Silver usando dbt com Trino para processar dados Iceberg.

## Estrutura

- `models/silver/` - Modelos da camada silver
- `macros/` - Macros customizadas para Trino/Iceberg
- `tests/` - Testes de qualidade de dados

## Execução

### Manual
```bash
docker-compose exec dbt-trino dbt run --models silver.*
docker-compose exec dbt-trino dbt test
```

### Automática
A DAG do Airflow `dbt_trino_silver_pipeline` executa a cada 2 minutos.

## Monitoramento

- Airflow UI: http://localhost:8086
- Trino UI: http://localhost:8080
EOF

# Definir permissões
echo "Ajustando permissões..."
chmod -R 755 dbt_iceberg/
chmod +x setup_dbt_trino.sh

# Construir imagem Docker
echo "Construindo imagem Docker do dbt-trino..."
docker build -t dbt-trino:latest -f services/dbt-trino/Dockerfile .

# Adicionar serviço ao docker-compose se não existir
if ! grep -q "dbt-trino:" docker-compose.yml; then
    echo ""
    echo "ATENÇÃO: Adicione os serviços dbt-trino ao seu docker-compose.yml"
    echo "O conteúdo está no arquivo: docker-compose-dbt-trino.yml"
    echo ""
fi

echo "=== Setup concluído! ==="
echo ""
echo "Próximos passos:"
echo "1. Adicione os serviços dbt-trino ao docker-compose.yml"
echo "2. Execute: docker-compose up -d dbt-trino dbt-trino-init"
echo "3. O Airflow executará automaticamente a cada 2 minutos"
echo "4. Monitore em http://localhost:8086"
echo ""
echo "Para executar manualmente:"
echo "  docker-compose exec dbt-trino dbt run --models silver.*"
echo "  docker-compose exec dbt-trino dbt test"