#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Variables
KAFKA_BROKER="kafka:9092"
KAFKA_TOPIC="dados_produtores"
MINIO_ALIAS="local"
MINIO_ENDPOINT="http://minio:9000"
MINIO_ACCESS_KEY="admin"
MINIO_SECRET_KEY="password"
MINIO_BUCKETS=("bronze" "silver" "gold" "warehouse")
DBT_PROJECT_DIR="/usr/app/dbt_project"

echo "=== Modern Data Pipeline Setup with Iceberg ==="
echo "Aguardando serviços ficarem disponíveis..."

echo "Verificando disponibilidade do Kafka..."
until docker-compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_BROKER --list > /dev/null 2>&1; do
  echo "Kafka não disponível ainda, aguardando..."
  sleep 5
done
echo "✓ Kafka está disponível."

echo "Criando tópico Kafka: $KAFKA_TOPIC..."
EXISTING_TOPICS=$(docker-compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_BROKER --list)
if echo "$EXISTING_TOPICS" | grep -q "^\s*$KAFKA_TOPIC\s*$"; then
  echo "✓ Tópico Kafka '$KAFKA_TOPIC' já existe."
else
  docker-compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_BROKER --create --topic $KAFKA_TOPIC --partitions 3 --replication-factor 1
  echo "✓ Tópico Kafka '$KAFKA_TOPIC' criado."
fi

echo "Verificando disponibilidade do MinIO..."
until docker-compose exec -T mc mc alias ls $MINIO_ALIAS > /dev/null 2>&1; do
    echo "MinIO não disponível ainda, aguardando..."
    sleep 3
done
echo "✓ MinIO está disponível."

echo "Criando buckets no MinIO..."
for bucket in "${MINIO_BUCKETS[@]}"; do
  if docker-compose exec -T mc mc ls "$MINIO_ALIAS/$bucket" > /dev/null 2>&1; then
    echo "✓ Bucket MinIO '$bucket' já existe."
  else
    docker-compose exec -T mc mc mb "$MINIO_ALIAS/$bucket"
    docker-compose exec -T mc mc policy set public "$MINIO_ALIAS/$bucket"
    echo "✓ Bucket MinIO '$bucket' criado e configurado como público."
  fi
done

echo "Verificando disponibilidade do Hive Metastore..."
until docker-compose exec -T hive-metastore bash -c "netstat -ln | grep 9083" > /dev/null 2>&1; do
    echo "Hive Metastore não disponível ainda, aguardando..."
    sleep 5
done
echo "✓ Hive Metastore está disponível."

echo "Verificando disponibilidade do Spark Master..."
until curl -s http://localhost:8080 > /dev/null 2>&1; do
    echo "Spark Master não disponível ainda, aguardando..."
    sleep 5
done
echo "✓ Spark Master está disponível."

echo "Verificando disponibilidade do ClickHouse..."
until docker-compose exec -T clickhouse clickhouse-client --query "SELECT 1" > /dev/null 2>&1; do
    echo "ClickHouse não disponível ainda, aguardando..."
    sleep 3
done
echo "✓ ClickHouse está disponível."

echo "Configurando databases iniciais no ClickHouse..."
docker-compose exec -T clickhouse clickhouse-client --query "CREATE DATABASE IF NOT EXISTS bronze"
docker-compose exec -T clickhouse clickhouse-client --query "CREATE DATABASE IF NOT EXISTS silver"
docker-compose exec -T clickhouse clickhouse-client --query "CREATE DATABASE IF NOT EXISTS gold"
docker-compose exec -T clickhouse clickhouse-client --query "CREATE DATABASE IF NOT EXISTS marts"
echo "✓ Databases do ClickHouse configurados."

echo "Verificando disponibilidade do Feast Serve..."
until nc -z localhost 6566; do
    echo "Feast Serve não disponível ainda, aguardando..."
    sleep 5
done
echo "✓ Feast Serve está disponível."

echo "Aplicando configuração do Feast..."
docker-compose exec -T feast-serve feast apply
echo "✓ Repositório Feast aplicado."

echo "Executando setup do dbt..."
docker-compose exec -T dbt dbt deps
docker-compose exec -T dbt dbt run --full-refresh
echo "✓ Setup do dbt concluído."

echo "Testando conectividade Iceberg..."
docker-compose exec -T spark-master /opt/bitnami/spark/bin/spark-sql \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3 \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog \
  --conf spark.sql.catalog.spark_catalog.type=hive \
  -e "CREATE DATABASE IF NOT EXISTS bronze; SHOW DATABASES;"
echo "✓ Iceberg configurado e testado."

# Download PostgreSQL JDBC Driver se necessário
DRIVER_DIR="./drivers"
DRIVER_JAR="postgresql-42.7.5.jar"
DRIVER_URL="https://jdbc.postgresql.org/download/postgresql-42.7.5.jar"

if [ ! -f "${DRIVER_DIR}/${DRIVER_JAR}" ]; then
  echo "Baixando driver PostgreSQL JDBC..."
  mkdir -p "${DRIVER_DIR}"
  if curl -L -o "${DRIVER_DIR}/${DRIVER_JAR}" "${DRIVER_URL}"; then
    echo "✓ Driver PostgreSQL JDBC baixado com sucesso."
  else
    echo "❌ Falha ao baixar driver PostgreSQL JDBC."
    exit 1
  fi
else
  echo "✓ Driver PostgreSQL JDBC já existe."
fi

echo ""
echo "=== Setup Concluído com Sucesso! ==="
echo ""
echo "🚀 Serviços Disponíveis:"
echo "   • MinIO Console: http://localhost:9001 (admin/password)"
echo "   • Spark Master UI: http://localhost:8080"
echo "   • Kafka UI: http://localhost:8085"
echo "   • Trino UI: http://localhost:8088"
echo "   • ClickHouse HTTP: http://localhost:8123"
echo "   • Superset: http://localhost:8089 (admin/admin)"
echo "   • Jupyter Lab: http://localhost:8888"
echo "   • Feast gRPC: localhost:6566"
echo ""
echo "📊 Para iniciar o pipeline de dados:"
echo "   1. O producer Avro está enviando dados para o tópico '$KAFKA_TOPIC'"
echo "   2. O consumer PySpark Streaming está consumindo e salvando em Iceberg"
echo "   3. Acesse Kafka UI para monitorar mensagens"
echo "   4. Use Trino/Superset para consultas analíticas"
echo ""
echo "🔍 Comandos úteis:"
echo "   • Verificar logs do streaming: docker-compose logs -f streaming-consumer"
echo "   • Executar dbt: docker-compose exec dbt dbt run"
echo "   • Query Iceberg via Spark: docker-compose exec spark-master /opt/bitnami/spark/bin/spark-sql"
echo ""
echo "✅ Pipeline pronto para uso!"