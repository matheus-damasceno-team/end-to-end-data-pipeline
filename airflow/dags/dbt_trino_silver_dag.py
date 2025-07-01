"""
DAG para executar transformações dbt na camada Silver usando Trino e Iceberg
Executa a cada 2 minutos para processar dados incrementalmente
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import logging

# Configurações padrão da DAG
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'email': ['admin@example.com'],
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
    'execution_timeout': timedelta(minutes=5),  # Mais rápido com Trino
}

# Configuração da DAG
dag = DAG(
    'dbt_trino_silver_pipeline',
    default_args=default_args,
    description='Pipeline Silver com dbt e Trino (Iceberg)',
    schedule_interval='*/2 * * * *',  # A cada 2 minutos
    catchup=False,
    max_active_runs=1,
    tags=['dbt', 'trino', 'silver', 'iceberg'],
)

def log_execution_info(**context):
    """Log informações sobre a execução"""
    logging.info(f"Iniciando pipeline Silver com Trino")
    logging.info(f"Data de execução: {context['execution_date']}")
    logging.info(f"Run ID: {context['dag_run'].run_id}")

# Task inicial de log
log_start = PythonOperator(
    task_id='log_start',
    python_callable=log_execution_info,
    provide_context=True,
    dag=dag,
)

# Task para executar dbt run
dbt_run_silver = DockerOperator(
    task_id='dbt_run_silver',
    image='modern-data-pipeline-dbt-trino:latest',
    force_pull=False,
    api_version='auto',
    auto_remove=True,
    mount_tmp_dir=False,
    command="""
    bash -c "
        cd /dbt && 
        echo '=== Executando dbt run incremental ===' &&
        dbt run --models silver.* --vars '{run_date: {{ ds }}}' &&
        echo '=== dbt run concluído com sucesso ==='
    "
    """,
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    mounts=[
        Mount(source='/home/matheus-damasceno/modern-data-pipeline/services/dbt-trino', target='/dbt', type='bind'),
        Mount(source='/tmp', target='/tmp', type='bind')
    ],
    environment={
        'DBT_PROFILES_DIR': '/dbt',
        'DBT_LOG_LEVEL': 'info'
    },
    dag=dag,
)

# Task para executar testes
dbt_test_silver = DockerOperator(
    task_id='dbt_test_silver',
    image='modern-data-pipeline-dbt-trino:latest',
    force_pull=False,
    api_version='auto',
    auto_remove=True,
    mount_tmp_dir=False,
    command="""
    bash -c "
        cd /dbt && 
        echo '=== Executando testes dbt ===' &&
        dbt test --models silver.* --store-failures &&
        echo '=== Testes concluídos ==='
    "
    """,
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    mounts=[
        Mount(source='/home/matheus-damasceno/modern-data-pipeline/services/dbt-trino', target='/dbt', type='bind'),
        Mount(source='/tmp', target='/tmp', type='bind')
    ],
    environment={
        'DBT_PROFILES_DIR': '/dbt'
    },
    dag=dag,
)

# Task para otimizar tabelas Iceberg via Trino
optimize_tables = DockerOperator(
    task_id='optimize_iceberg_tables',
    image='trinodb/trino:450',
    api_version='auto',
    auto_remove=True,
    command="""
    trino --server trino:8080 --catalog iceberg --schema silver --execute "
        ALTER TABLE silver_dados_produtores_agro_trino EXECUTE optimize(file_size_threshold => '100MB');
        ANALYZE silver_dados_produtores_agro_trino;
    "
    """,
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    dag=dag,
)

# Task para coletar métricas
collect_metrics = DockerOperator(
    task_id='collect_metrics',
    image='trinodb/trino:450',
    api_version='auto',
    auto_remove=True,
    command="""
    trino --server trino:8080 --catalog iceberg --schema silver --execute "
        SELECT 
            'silver_dados_produtores_agro_trino' as table_name,
            COUNT(*) as total_rows,
            COUNT(DISTINCT proponente_id) as unique_proponentes,
            MAX(ingestion_timestamp) as last_ingestion,
            CURRENT_TIMESTAMP as metric_timestamp
        FROM silver_dados_produtores_agro_trino;
    "
    """,
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    dag=dag,
)



# Task final
log_end = PythonOperator(
    task_id='log_end',
    python_callable=lambda **context: logging.info("Pipeline Silver concluído com sucesso"),
    trigger_rule='none_failed',
    dag=dag,
)

log_start >> dbt_run_silver >> dbt_test_silver >> optimize_tables >> collect_metrics >> log_end