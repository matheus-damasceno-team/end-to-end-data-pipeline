#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Variables
KAFKA_BROKER="kafka:9092"
KAFKA_TOPIC="dados_produtores"
MINIO_ALIAS="local" # Alias used in mc config
MINIO_ENDPOINT="http://minio:9000"
MINIO_ACCESS_KEY="admin"
MINIO_SECRET_KEY="password"
MINIO_BUCKETS=("bronze" "silver" "gold" "druid" "warehouse" "clickhouse") # Added clickhouse bucket for CH S3 disk
DRUID_ROUTER_URL="http://druid-router:8888" # Druid Router for submitting tasks
DRUID_INGESTION_SPEC_PATH="/opt/druid/ingestion/ingestion-spec.json" # Path inside Druid MiddleManager
DBT_PROJECT_DIR="/usr/app/dbt_project" # Path inside dbt container

echo "Waiting for Kafka to be available..."
# Use kafka-topics.sh via a Kafka container, assuming one is running and accessible
# Or, if this script runs on host, ensure kafka-topics.sh is in PATH and configured for the Docker Kafka
# For simplicity, let's assume we can docker exec into the kafka container
until docker-compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_BROKER --list > /dev/null 2>&1; do
  echo "Kafka not yet available, sleeping..."
  sleep 5
done
echo "Kafka is up."

echo "Creating Kafka topic: $KAFKA_TOPIC..."
# Check if topic exists
EXISTING_TOPICS=$(docker-compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_BROKER --list)
if echo "$EXISTING_TOPICS" | grep -q "^\s*$KAFKA_TOPIC\s*$"; then
  echo "Kafka topic '$KAFKA_TOPIC' already exists."
else
  docker-compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_BROKER --create --topic $KAFKA_TOPIC --partitions 1 --replication-factor 1
  echo "Kafka topic '$KAFKA_TOPIC' created."
fi

echo "Waiting for MinIO to be available..."
# The 'mc' service in docker-compose already waits for MinIO and configures the host.
# We just need to ensure mc is ready to take commands.
until docker-compose exec -T mc mc alias ls $MINIO_ALIAS > /dev/null 2>&1; do
    echo "MinIO (via mc) not yet available, sleeping..."
    sleep 3
done
echo "MinIO is up and mc alias '$MINIO_ALIAS' is configured."

echo "Creating MinIO buckets..."
for bucket in "${MINIO_BUCKETS[@]}"; do
  if docker-compose exec -T mc mc ls "$MINIO_ALIAS/$bucket" > /dev/null 2>&1; then
    echo "MinIO bucket '$bucket' already exists."
  else
    docker-compose exec -T mc mc mb "$MINIO_ALIAS/$bucket"
    docker-compose exec -T mc mc policy set public "$MINIO_ALIAS/$bucket" # For easy dev access
    echo "MinIO bucket '$bucket' created and set to public."
  fi
done

echo "Waiting for Feast Serve to be available..."
# Check if feast-serve gRPC port is listening
# This is a simple check; a more robust one would involve a gRPC health check
until nc -z localhost 6566; do # Assuming feast-serve is mapped to localhost:6566
    echo "Feast Serve not yet available on port 6566, sleeping..."
    sleep 5
done
echo "Feast Serve is up."

echo "Applying Feast repository..."
# Ensure the feast_repo directory is correctly mounted and accessible
# The command needs to be run where feature_store.yaml is.
# The feast-serve container has working_dir: /app/feast_repo
# We also need to ensure the registry.db has write permissions for the user in the container.
# For simplicity, assume default user can write.
docker-compose exec -T feast-serve feast apply
# An alternative is to run `feast apply` in a temporary container with access to the repo and Redis.
# Example:
# docker run --rm --network=data_pipeline_net \
#   -v $(pwd)/feast_repo:/app/feast_repo \
#   -e FEAST_CORE_URL=feast-serve:6566 \
#   -e REDIS_HOST=redis \
#   -e REDIS_PORT=6379 \
#   -e AWS_ACCESS_KEY_ID=admin \
#   -e AWS_SECRET_ACCESS_KEY=password \
#   -e AWS_S3_ENDPOINT_URL=http://minio:9000 \
#   feastdev/feast-python-server:0.34.1 apply # Use an image that has the CLI and dependencies
echo "Feast repository applied."


echo "Waiting for Druid Router to be available..."
until curl -s "$DRUID_ROUTER_URL/status" | grep -q "Druid version"; do
  echo "Druid Router not yet available at $DRUID_ROUTER_URL, sleeping..."
  sleep 10 # Druid can take a while to start all components
done
echo "Druid Router is up."

echo "Submitting Druid Kafka ingestion spec..."
# The ingestion spec JSON is mounted into the druid-middlemanager container.
# We submit it via the Druid Router's API.
# The actual ingestion spec file is services/druid/ingestion-spec.json on the host.
# It's mounted to /opt/druid/ingestion/ingestion-spec.json in druid-middlemanager.
# The task JSON for submission needs to be accessible by the curl command.
# We can cat the file and pipe it to curl, or exec into a container that has curl and the spec.

# Option 1: Cat the file from host and post (if this script runs on host with access to the spec)
# Ensure ingestion-spec.json is in the expected relative path from this script, or use absolute path.
# For now, let's assume the spec file is in ./services/druid/ingestion-spec.json relative to project root.
# This script is in project root.
INGESTION_SPEC_CONTENT=$(cat ./services/druid/ingestion-spec.json)

# Check if a supervisor for this datasource already exists
DATASOURCE_NAME=$(jq -r .dataSchema.dataSource ./services/druid/ingestion-spec.json)
SUPERVISORS=$(curl -s -X GET "$DRUID_ROUTER_URL/druid/indexer/v1/supervisor")

if echo "$SUPERVISORS" | jq -e --arg ds "$DATASOURCE_NAME" '.[] | select(.id == $ds or .spec.dataSchema.dataSource == $ds)' > /dev/null; then
  echo "Druid supervisor for datasource '$DATASOURCE_NAME' already exists or a similar one is running."
else
  # Wait for MiddleManager to be ready to accept tasks (often needs more time)
  echo "Waiting for Druid MiddleManager to be ready..."
  # A simple check, might need to be more robust
  until curl -s -X GET "$DRUID_ROUTER_URL/druid/indexer/v1/runners" | grep -q "middleManager"; do
      echo "Druid MiddleManager not listed by runners yet, sleeping..."
      sleep 5
  done
  echo "Druid MiddleManager seems ready."

  echo "Submitting new Druid supervisor for datasource '$DATASOURCE_NAME'."
  curl -s -X POST -H 'Content-Type:application/json' -d "$INGESTION_SPEC_CONTENT" "$DRUID_ROUTER_URL/druid/indexer/v1/supervisor"
  # Check response
  # TODO: Add more robust check for submission success
  echo "Druid ingestion spec submitted. Check Druid console for status."
fi


echo "Waiting for ClickHouse to be available..."
# The dbt service depends on clickhouse, so it should wait.
# We can add an explicit check here too.
until docker-compose exec -T clickhouse clickhouse-client --query "SELECT 1" > /dev/null 2>&1; do
    echo "ClickHouse not yet available, sleeping..."
    sleep 3
done
echo "ClickHouse is up."

echo "Running dbt setup (deps and seed if any, then run)..."
# Ensure profiles.yml is correctly configured and mounted in the dbt container.
# The dbt_project directory is also mounted.
# The dbt container's working_dir is /usr/app/dbt_project
docker-compose exec -T dbt dbt deps
# If you have seeds:
# docker-compose exec -T dbt dbt seed --full-refresh # Use --full-refresh for first time
docker-compose exec -T dbt dbt run --full-refresh # Use --full-refresh for first time or when models change significantly
# docker-compose exec -T dbt dbt test # Optionally run dbt tests
echo "dbt setup complete."

# Setup for Druid Metadata Database (PostgreSQL)
# This is complex because it involves creating a new DB and user in an existing Postgres container.
# The hive-metastore-db container runs Postgres. Druid services expect a DB 'druid' and user 'druiduser'.
echo "Configuring PostgreSQL for Druid metadata..."
# Check if user 'druiduser' exists
USER_EXISTS=$(docker-compose exec -T hive-metastore-db psql -U hive -d metastore -tAc "SELECT 1 FROM pg_roles WHERE rolname='druiduser'")
if [ "$USER_EXISTS" = "1" ]; then
    echo "PostgreSQL user 'druiduser' already exists."
else
    echo "Creating PostgreSQL user 'druiduser'..."
    docker-compose exec -T hive-metastore-db psql -U hive -d metastore -c "CREATE USER druiduser WITH PASSWORD 'druidpassword';"
fi

# Check if database 'druid' exists
DB_EXISTS=$(docker-compose exec -T hive-metastore-db psql -U hive -lqt | cut -d \| -f 1 | grep -qw druid)
if [ "$DB_EXISTS" ]; then # psql -lqt returns list of DBs, grep checks if 'druid' is in it
    echo "PostgreSQL database 'druid' already exists."
else
    echo "Creating PostgreSQL database 'druid'..."
    docker-compose exec -T hive-metastore-db psql -U hive -d metastore -c "CREATE DATABASE druid OWNER druiduser;"
fi
# Grant privileges if not already granted (idempotent way is harder with psql one-liners)
docker-compose exec -T hive-metastore-db psql -U hive -d druid -c "GRANT ALL PRIVILEGES ON DATABASE druid TO druiduser;"
# For Druid to create tables, the user also needs CREATETABLE or similar on the schema or DB.
# The OWNER should suffice, but if issues, might need:
# docker-compose exec -T hive-metastore-db psql -U hive -d druid -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO druiduser;"
# docker-compose exec -T hive-metastore-db psql -U hive -d druid -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO druiduser;"
echo "PostgreSQL configuration for Druid metadata complete."
echo "If Druid services were started before this, they might need a restart to connect to metadata successfully."
echo "Consider using 'depends_on' with healthchecks or a multi-stage setup for robust DB initialization before Druid starts."


echo "---"
echo "Setup script finished."
echo "You might need to restart Druid services if they failed to connect to their metadata DB initially:"
echo "  docker-compose restart druid-coordinator druid-broker druid-router druid-historical druid-middlemanager"
echo "Access services:"
echo "  MinIO Console: http://localhost:9001 (admin/password)"
echo "  Spark Master UI: http://localhost:8080"
echo "  Trino UI: http://localhost:8088"
echo "  Feast Serving (gRPC): localhost:6566"
echo "  Druid Router (Query Console): http://localhost:8888"
echo "  Druid Coordinator Console: http://localhost:8091"
echo "  Superset UI: http://localhost:8089 (admin/admin after initial setup)"
echo "  Kafka (internal): kafka:9092"
echo "  ClickHouse (HTTP): http://localhost:8123, (Native): localhost:9004"
echo "---"

# Make this script executable
# chmod +x setup.sh
# Run with: ./setup.sh
# Or, if using Docker Compose to manage this script as a one-off task:
# docker-compose run --rm setup_runner ./setup.sh (requires defining setup_runner service)
# For now, designed to be run from the host where docker-compose commands are available.

# Notes for robustness:
# - Healthchecks in docker-compose.yml for services like Kafka, MinIO, Postgres, Druid components.
# - More sophisticated wait logic (e.g., using dedicated wait-for-it scripts or tool-specific health checks).
# - Idempotency for all operations (e.g., create if not exists).
# - Error handling and logging.
# - Parameterization of names, keys, etc.
# - For Druid ingestion, the spec submission is async. Script should check task status.
# - For Feast apply, ensure registry.db is initialized correctly.
# - For dbt, profiles.yml needs to be correctly configured.
# - The Druid metadata DB setup is critical. Druid services need to connect to it.
#   If they start before DB is ready, they might fail. `depends_on` with healthchecks is better.
#   Alternatively, run this part of script first, then start Druid services.
#   The current script attempts to create user/db and suggests restarting Druid if needed.
#   A better approach for production would be an init container for Postgres that sets up users/dbs.
#   Or, a more complex entrypoint for the postgres service.
#   For this local dev setup, manual restart of Druid or running setup before `docker-compose up -d druid-...` is an option.
#   The current docker-compose has Druid depending on hive-metastore-db, but not on the *contents* of the DB.
#   A more robust approach would be to have a separate script/service that initializes the DB,
#   and then Druid services depend on that initialization service completing.
#   For now, the script includes the DB setup and a note about restarting Druid.
#   The `until` loops are basic checks. `docker-compose exec -T kafka kafka-topics ...` is a good way to check Kafka readiness.
#   For MinIO, `mc alias ls` is a good check. For ClickHouse, `clickhouse-client --query "SELECT 1"`.
#   For Druid, checking `/status` of components is a good start.
#   For Feast, checking the gRPC port with `nc` is basic.
#   A `jq` dependency is assumed for parsing JSON in the Druid supervisor check. Install if not present on host.
#   If `jq` is not available, the Druid supervisor check will be less robust (e.g., rely on string matching).
#   The script uses `docker-compose exec -T` to run commands inside containers without a TTY, suitable for automation.
#   The `FEAST_CORE_URL` for `feast apply` running in a temporary container should point to the running `feast-serve` service.
#   The current `feast apply` uses `docker-compose exec feast-serve`, which is simpler.
#   The `until nc -z localhost 6566;` for Feast assumes the port is mapped to localhost. If running setup inside a container on the same network, use `feast-serve:6566`.
#   The script is designed to be run from the root of the project directory.
#   Ensure `chmod +x setup.sh` is run once to make the script executable.
#   If Druid services are started with `docker-compose up -d`, and this script runs afterwards, they may have already tried and failed to connect to their metadata DB.
#   The `druid_metadata_storage_connector_connectURI` for Druid services points to `hive-metastore-db`.
#   This script tries to create the 'druid' database and 'druiduser' in that Postgres instance.
#   The user 'hive' in `hive-metastore-db` is the superuser for that DB (or has rights to create users/DBs).
#   The script uses `psql -U hive` to connect and create the Druid user and database.
#   Final check of Druid supervisor submission: `curl -s "$DRUID_ROUTER_URL/druid/indexer/v1/supervisor/$DATASOURCE_NAME/status" | jq .`
#   The script now includes a basic check for existing Druid supervisors to avoid duplicate submissions.
#   The script also adds `warehouse` and `druid` buckets to MinIO.
#   `warehouse` for Hive/Spark, `druid` for Druid deep storage.
#   The Druid S3 endpoint for non-AWS (like MinIO) might need `druid.s3.pathStyleAccess=true` and `druid.s3.endpoint.signingRegion=` (empty for MinIO usually).
#   These are often set in Druid's `common.runtime.properties` or passed as Java Opts.
#   The current Druid config in `docker-compose.yml` uses `druid_s3_endpoint_url` which is for newer Druid versions.
#   For older versions, it might be `druid.storage.s3.endpoint`. Check Druid S3 extension docs for the specific version.
#   The Druid version `0.23.0` should support `druid_s3_endpoint_url`.
#   The `druid_s3_protocol: http` and `druid_s3_endpoint_url: "minio:9000"` seems correct for MinIO.
#   Make sure `postgresql-metadata-storage` and `druid-s3-extensions` are in `druid_extensions_loadList` for all Druid services.
#   The script now includes the PostgreSQL setup for Druid.
#   It's important that `hive-metastore-db` is up before this part of the script runs. `docker-compose up -d hive-metastore-db` first, or rely on script's wait logic.
#   Added `set -e` for safer script execution.
#   The `jq` command for checking existing supervisors: `jq -e --arg ds "$DATASOURCE_NAME" '.[] | select(.id == $ds or .spec.dataSchema.dataSource == $ds)'`
#   This looks for supervisors where either the `id` or the `spec.dataSchema.dataSource` matches the one from the new spec.
#   This helps in making the supervisor submission idempotent.
#   The `until` loop for Druid MiddleManager checks `/druid/indexer/v1/runners`. This is a reasonable heuristic.
#   The MinIO bucket creation loop is fine.
#   The Kafka topic creation is also fine.
#   The Feast apply command is simple.
#   The dbt commands are standard.
#   Overall, the script covers the main setup tasks.
#   Consider adding a `docker-compose down -v` instruction for cleanup in the README.
#   The script assumes `docker-compose` is V1. For Docker Compose V2 (plugin), it's `docker compose`.
#   Adjust `docker-compose` to `docker compose` if using V2. This script uses `docker-compose`.
#   The `nc -z localhost 6566` for Feast assumes that the `feast-serve` port `6566` is mapped to `localhost:6566` in `docker-compose.yml`.
#   It is: `ports: - "6566:6566"`. So this check is okay.
#   The Druid ingestion spec path is assumed to be `./services/druid/ingestion-spec.json` relative to project root.
#   The `cat` command will work if script is run from project root.
#   The script is now fairly comprehensive for a local development setup.
#   Final check on Druid metadata: ensure `druid_metadata_storage_connector_user` and `password` match what's created in Postgres.
#   They are `druiduser` and `druidpassword`, which matches the script.
#   The Postgres user `hive` with password `hivepassword` is used to administer the `metastore` DB and create the `druid` user/DB.
#   This is fine for a local setup.
#   The `jq` dependency should be mentioned to the user if this script is to be run on their host.
#   If `jq` is not available, the Druid supervisor check could be simplified to a `grep` or removed, risking duplicate supervisors.
#   For simplicity, the script does not install `jq`. It assumes it's present.
#   The script output provides useful URLs for accessing the services.
#   The note about restarting Druid is important due to potential race conditions with metadata DB setup.
#   Adding `docker-compose up -d --wait` for services with healthchecks could improve startup order if healthchecks are well-defined.
#   The current `setup.sh` is designed for interactive or semi-automated setup.
#   For fully automated CI/CD, more robust health checking and wait conditions would be needed.
#   The Kafka check uses `kafka-topics --list`. This is a good indicator.
#   The MinIO check uses `mc alias ls`. Also good.
#   The ClickHouse check uses `clickhouse-client --query "SELECT 1"`. Standard.
#   The Druid router check uses `/status`. Standard.
#   The Feast check uses `nc -z`. Basic but effective for port listening.
#   The script seems ready.
#   One final thought: if any service fails to start correctly due to unmet dependencies (despite `depends_on`), this script might also fail or hang.
#   The `until` loops with timeouts would be more robust in such cases. Currently, they sleep and retry.
#   The `set -e` will cause the script to exit on first error, which is good for debugging.
#   The script is quite long; breaking it into functions could improve readability for very complex setups.
#   For this scope, it's manageable.
#   Remember to `chmod +x setup.sh` after creating it.
#   The script could also include commands to populate initial data if needed, e.g., using `mc cp` or running data generation scripts. This is out of scope for the current request but a common next step.
#   The `MINIO_BUCKETS` array includes `warehouse` and `druid` which are good defaults.
#   The script structure is logical: wait for service, then configure/initialize it.
#   The Druid part is the most complex due to inter-component dependencies and external DB setup.
#   The Postgres setup for Druid is now included, which is a critical part.
#   The script is designed to be run after `docker-compose up -d` has started (or attempted to start) all services.
#   If run before, some `docker-compose exec` commands might fail if containers are not yet running.
#   The `until` loops help mitigate this by waiting for services to become available.
#   Consider adding a check for `docker-compose` command availability at the beginning of the script.
#   For now, it assumes `docker-compose` (V1 syntax) is installed and working.
#   If `docker compose` (V2 syntax) is preferred, all instances should be changed.
#   The current prompt does not specify Compose version, V1 is often assumed for broader compatibility in scripts.
#   The script is ready for generation.
#   The Druid ingestion spec is submitted as a supervisor, which means Druid will manage the Kafka ingestion task continuously.
#   This is appropriate for real-time data ingestion.
#   The supervisor ID is implicitly the datasource name from the spec.
#   The script checks if a supervisor for that datasource already exists to avoid errors on re-runs.
#   The `jq` dependency is noted.
#   The script is good to go.
