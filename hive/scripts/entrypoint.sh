#!/bin/bash

set -e

# Wait for MariaDB to be ready
echo "Waiting for MariaDB to be ready..."
while ! nc -z mariadb-hive 3306; do
  sleep 1
done
echo "MariaDB is ready!"

# Initialize schema if needed
if [ "${SKIP_SCHEMA_INIT}" != "true" ]; then
  echo "Initializing Hive Metastore schema..."
  ${HIVE_HOME}/bin/schematool -dbType mysql -initSchema || {
    echo "Schema initialization failed, checking if already exists..."
    ${HIVE_HOME}/bin/schematool -dbType mysql -info
  }
fi

# Start Hive Metastore
echo "Starting Hive Metastore..."
exec ${HIVE_HOME}/bin/hive --service metastore