#!/bin/bash
set -e

echo "Waiting for metastore database to be ready..."
sleep 5

# Verifica se o schema já foi inicializado
echo "Checking if Hive Metastore schema already exists..."

# Testa a conexão com o banco e verifica se as tabelas existem
if /opt/hive/bin/schematool -dbType mysql -info > /dev/null 2>&1; then
    echo "Hive Metastore schema already exists and is valid."
    echo "Schema initialization skipped."
else
    echo "Hive Metastore schema not found or invalid. Initializing..."
    /opt/hive/bin/schematool -dbType mysql -initSchema
    echo "Schema initialized successfully!"
fi

echo "Metastore schema setup completed."