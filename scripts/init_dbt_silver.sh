#!/bin/bash
# Script de inicialização do dbt para camada Silver com Iceberg

set -e

echo "=== Iniciando configuração do dbt Silver com Iceberg ==="

# Verificar se os arquivos dbt já existem
if [ ! -f "/dbt/dbt_project.yml" ]; then
    echo "Copiando arquivos de configuração do dbt..."
    
    # Copiar todos os arquivos necessários
    cp -r /tmp/dbt_configs/* /dbt/ 2>/dev/null || true
fi

# Instalar dependências do dbt
echo "Instalando dependências do dbt..."
cd /dbt
dbt deps

# Criar database silver se não existir
echo "Criando database silver no Hive Metastore..."
/opt/spark/bin/spark-sql \
    --master local[*] \
    --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
    --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkCatalog \
    --conf spark.sql.catalog.spark_catalog.type=hive \
    --conf spark.sql.catalog.spark_catalog.uri=thrift://metastore:9083 \
    --conf spark.sql.catalog.spark_catalog.warehouse=s3a://warehouse \
    --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
    --conf spark.hadoop.fs.s3a.access.key=admin \
    --conf spark.hadoop.fs.s3a.secret.key=password \
    --conf spark.hadoop.fs.s3a.path.style.access=true \
    -e "CREATE DATABASE IF NOT EXISTS silver"

echo "=== Configuração concluída ==="
echo ""
echo "Executando primeira transformação dbt..."
dbt run --models silver.* --full-refresh

echo ""
echo "Executando testes..."
dbt test --models silver.*

echo ""
echo "=== dbt Silver está pronto! ==="
echo "A DAG do Airflow executará automaticamente a cada 2 minutos"
echo "Acesse http://localhost:8086 para monitorar no Airflow"