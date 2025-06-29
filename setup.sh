#!/bin/bash
# Arquivo: setup.sh
# Script completo de configuração do Modern Data Pipeline

set -e

# ========================================================================================
# VARIÁVEIS DE CONFIGURAÇÃO
# ========================================================================================

KAFKA_BROKER="kafka:9092"
KAFKA_TOPIC="dados_produtores"
MINIO_ALIAS="local"
MINIO_ENDPOINT="http://minio:9000"
MINIO_ACCESS_KEY="admin"
MINIO_SECRET_KEY="password"
MINIO_BUCKETS=("bronze" "silver" "gold" "warehouse" "clickhouse")
DBT_PROJECT_DIR="/usr/app/dbt_project"

# ========================================================================================
# FUNÇÕES UTILITÁRIAS
# ========================================================================================

log_info() {
    echo "ℹ️  $1"
}

log_success() {
    echo "✅ $1"
}

log_warning() {
    echo "⚠️  $1"
}

log_error() {
    echo "❌ $1"
}

log_section() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
    echo ""
}

wait_for_service() {
    local service_name="$1"
    local check_command="$2"
    local max_attempts="${3:-10}"
    local attempt=1
    
    log_info "Waiting for $service_name to be available..."
    
    while [ $attempt -le $max_attempts ]; do
        if eval "$check_command" >/dev/null 2>&1; then
            log_success "$service_name is ready!"
            return 0
        fi
        
        echo "  Attempt $attempt/$max_attempts - $service_name not ready, waiting..."
        sleep 5
        ((attempt++))
    done
    
    log_error "$service_name failed to become available after $max_attempts attempts"
    return 1
}

check_dependency() {
    local dep_name="$1"
    local check_command="$2"
    
    if eval "$check_command" >/dev/null 2>&1; then
        log_success "$dep_name is available"
        return 0
    else
        log_error "$dep_name is not available"
        return 1
    fi
}

# ========================================================================================
# CRIAÇÃO DE ARQUIVOS DE CONFIGURAÇÃO
# ========================================================================================

create_directories() {
    log_section "CREATING DIRECTORY STRUCTURE"
    
    local dirs=(
        "scripts"
        "drivers"
        "notebooks"
        "dbt_project"
        "feast_repo"
        "trino_config/catalog"
        "clickhouse_config"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
        log_success "Created directory: $dir"
    done
}

download_drivers() {
    log_section "DOWNLOADING REQUIRED DRIVERS"
    
    # PostgreSQL JDBC Driver
    local driver_dir="./drivers"
    local driver_jar="postgresql-42.7.5.jar"
    local driver_url="https://jdbc.postgresql.org/download/postgresql-42.7.5.jar"

    if [ ! -f "${driver_dir}/${driver_jar}" ]; then
        log_info "Downloading PostgreSQL JDBC driver..."
        if curl -L -o "${driver_dir}/${driver_jar}" "${driver_url}"; then
            log_success "PostgreSQL JDBC driver downloaded to ${driver_dir}/${driver_jar}"
        else
            log_error "Failed to download PostgreSQL JDBC driver"
            log_info "Please download manually from: $driver_url"
            return 1
        fi
    else
        log_success "PostgreSQL JDBC driver already exists"
    fi
}

# ========================================================================================
# CONFIGURAÇÃO DE SERVIÇOS
# ========================================================================================

setup_kafka() {
    log_section "SETTING UP KAFKA"
    
    wait_for_service "Kafka" "docker compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_BROKER --list"
    
    log_info "Creating Kafka topic: $KAFKA_TOPIC"
    local existing_topics=$(docker compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_BROKER --list)
    
    if echo "$existing_topics" | grep -q "^\s*$KAFKA_TOPIC\s*$"; then
        log_info "Kafka topic '$KAFKA_TOPIC' already exists"
    else
        docker compose exec -T kafka kafka-topics --bootstrap-server $KAFKA_BROKER --create --topic $KAFKA_TOPIC --partitions 3 --replication-factor 1
        log_success "Kafka topic '$KAFKA_TOPIC' created with 3 partitions"
    fi
}

setup_minio() {
    log_section "SETTING UP MINIO"
    
    wait_for_service "MinIO mc" "docker compose exec -T mc mc alias ls $MINIO_ALIAS"
    
    log_info "Creating MinIO buckets..."
    for bucket in "${MINIO_BUCKETS[@]}"; do
        if docker compose exec -T mc mc ls "$MINIO_ALIAS/$bucket" >/dev/null 2>&1; then
            log_info "MinIO bucket '$bucket' already exists"
        else
            docker compose exec -T mc mc mb "$MINIO_ALIAS/$bucket"
            docker compose exec -T mc mc policy set public "$MINIO_ALIAS/$bucket"
            log_success "MinIO bucket '$bucket' created and set to public"
        fi
    done
}

setup_clickhouse() {
    log_section "SETTING UP CLICKHOUSE"
    
    wait_for_service "ClickHouse" "docker compose exec -T clickhouse clickhouse-client --query 'SELECT 1'"
    
    log_success "ClickHouse is ready"
}

setup_dbt() {
    log_section "SETTING UP DBT"
    
    log_info "Running dbt setup..."
    docker compose exec -T dbt dbt deps 2>/dev/null || log_warning "dbt deps failed or not needed"
    docker compose exec -T dbt dbt run --full-refresh 2>/dev/null || log_warning "dbt run failed - check configuration"
    
    log_info "dbt setup attempted"
}

setup_feast() {
    log_section "SETTING UP FEAST"
    
    wait_for_service "Feast Serve" "nc -z localhost 6566" 15
    
    log_info "Applying Feast repository..."
    docker compose exec -T feast-serve feast apply 2>/dev/null || log_warning "Feast apply failed - check configuration"
    
    log_info "Feast repository applied"
}

# ========================================================================================
# VERIFICAÇÃO E DIAGNÓSTICO
# ========================================================================================

check_service_health() {
    local service_name="$1"
    local url="$2"
    local expected_pattern="$3"
    
    if curl -s -f "$url" | grep -q "$expected_pattern" 2>/dev/null; then
        log_success "$service_name is healthy"
        return 0
    else
        log_warning "$service_name is not responding correctly"
        return 1
    fi
}

run_health_checks() {
    log_section "PERFORMING HEALTH CHECKS"
    
    log_info "Checking service health..."
    
    sleep 30
    check_service_health "Trino UI" "http://localhost:8088/ui/" "Trino"
    check_service_health "Spark Master UI" "http://localhost:8080" "Spark Master"
    check_service_health "MinIO Console" "http://localhost:9001/login" "MinIO"
}

show_service_urls() {
    log_section "SERVICE ACCESS URLS"
    
    echo "📊 MinIO Console: http://localhost:9001 (admin/password)"
    echo "🔥 Spark Master UI: http://localhost:8080"
    echo "🐘 Trino UI: http://localhost:8088"
    echo "🍽️  Feast Serving (gRPC): localhost:6566"
    echo "📈 Superset UI: http://localhost:8089"
    echo "🏠 ClickHouse (HTTP): http://localhost:8123"
    echo "📓 Jupyter Lab: http://localhost:8888"
    echo "🔗 Kafka UI: http://localhost:8085"
}

show_final_notes() {
    log_section "IMPORTANT NOTES AND NEXT STEPS"
    
    echo "✅ All services should now be running with proper configuration"
    echo "✅ Kafka topic '$KAFKA_TOPIC' is ready for producers"
    echo "✅ MinIO buckets are created and publicly accessible"
    echo ""
    echo "🔍 TROUBLESHOOTING:"
    echo "• If any service fails, check logs: docker compose logs [service-name]"
    echo "• View all logs: docker compose logs -f"
    echo "• Restart services: docker compose restart"
    echo ""
    echo "📋 NEXT STEPS:"
    echo "1. Start your data producers to send data to Kafka topic '$KAFKA_TOPIC'"
    echo "2. Query your data through Trino at: http://localhost:8088"
    echo "3. Build dashboards in Superset at: http://localhost:8089"
    echo ""
    echo "🚀 Quick verification commands:"
    echo "• Check container status: docker compose ps"
}

# ========================================================================================
# FUNÇÃO PRINCIPAL
# ========================================================================================

start_base_services() {
    log_section "STARTING BASE SERVICES"
    
    log_info "Starting all services with docker compose..."
    docker compose up -d
    
    log_info "Waiting for base services to initialize..."
    sleep 10
    
    log_success "Base services started successfully"
}

main() {
    log_section "MODERN DATA PIPELINE SETUP"
    log_info "Starting complete environment setup..."
    
    # Verificar dependências
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker compose >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    log_success "Dependencies check passed"
    
    # Preparar configurações
    create_directories
    download_drivers
    
    # INICIAR TODOS OS SERVIÇOS
    start_base_services  # DOCKER COMPOSE UP -D
    
    # Configurar serviços específicos
    setup_kafka
    setup_minio
    setup_clickhouse
    setup_dbt
    setup_feast
    
    # Verificação final
    run_health_checks
    show_service_urls
    show_final_notes
    
    log_section "SETUP COMPLETED SUCCESSFULLY! 🎉"
}

# ========================================================================================
# EXECUÇÃO
# ========================================================================================

# Executar função principal se script for chamado diretamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi