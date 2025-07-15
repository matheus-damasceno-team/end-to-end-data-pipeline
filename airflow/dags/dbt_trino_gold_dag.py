"""
DAG para executar transformações dbt na camada Gold (Feature Store) usando Trino e Iceberg
Pipeline de feature engineering baseado na camada Silver
Executa a cada 15 minutos para processar features incrementalmente
"""

from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import logging
import os

# Configurações padrão da DAG
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'email': ['admin@example.com'],
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=15),
}

# Construa o caminho dinâmico ANTES de definir o operador
# Use a variável de ambiente PROJECT_ROOT definida no docker-compose
project_root = os.getenv('PROJECT_ROOT', os.getcwd())
dbt_project_path = str(Path(project_root) / 'services' / 'dbt-trino')

# Configuração da DAG
dag = DAG(
    'dbt_trino_gold_feature_store',
    default_args=default_args,
    description='Pipeline Gold - Feature Store com dbt, Trino e Feast',
    schedule_interval='*/15 * * * *',  # A cada 15 minutos
    catchup=False,
    max_active_runs=1,
    tags=['dbt', 'trino', 'gold', 'iceberg', 'feast', 'feature-store'],
)

def log_execution_info(**context):
    """Log informações sobre a execução"""
    logging.info(f"Iniciando pipeline Gold - Feature Store")
    logging.info(f"Data de execução: {context['execution_date']}")
    logging.info(f"Run ID: {context['dag_run'].run_id}")
    logging.info(f"Processando features da camada Silver")

def log_completion_info(**context):
    """Log informações de conclusão"""
    logging.info(f"Pipeline Gold - Feature Store concluído com sucesso")
    logging.info(f"Features disponíveis para serving via Feast")
    logging.info(f"Próxima execução em 15 minutos")

# Task inicial de log
log_start = PythonOperator(
    task_id='log_start',
    python_callable=log_execution_info,
    provide_context=True,
    dag=dag,
)

# Task para executar dbt run na camada Gold
dbt_run_gold = DockerOperator(
    task_id='dbt_run_gold',
    image='modern-data-pipeline-dbt-trino:latest',
    force_pull=False,
    api_version='auto',
    auto_remove=True,
    mount_tmp_dir=False,
    command="""
    bash -c "
        cd /dbt && 
        echo '=== Executando dbt run camada Gold (Feature Store) ===' &&
        echo 'dbt run --target prod --models gold.* --vars {run_date: {{ ds }}}'
        dbt run --target prod --models gold.* --vars '{run_date: {{ ds }}}' &&
        echo '=== Features Gold geradas com sucesso ==='
    "
    """,
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    mounts=[
        Mount(source=dbt_project_path, target='/dbt', type='bind')
    ],
    environment={
        'DBT_PROFILES_DIR': '/dbt',
        'DBT_LOG_LEVEL': 'info'
    },
    dag=dag,
)

# Task para executar testes na camada Gold
dbt_test_gold = DockerOperator(
    task_id='dbt_test_gold',
    image='modern-data-pipeline-dbt-trino:latest',
    force_pull=False,
    api_version='auto',
    auto_remove=True,
    mount_tmp_dir=False,
    command="""
    bash -c "
        cd /dbt && 
        echo '=== Executando testes dbt camada Gold ===' &&
        dbt test --models gold.* --store-failures &&
        echo '=== Testes Gold concluídos com sucesso ==='
    "
    """,
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    mounts=[
        Mount(source=dbt_project_path, target='/dbt', type='bind')
    ],
    environment={
        'DBT_PROFILES_DIR': '/dbt'
    },
    dag=dag,
)

# Task para exportar features para o formato Parquet (para Feast)
export_features_to_parquet = DockerOperator(
    task_id='export_features_to_parquet',
    image='python:3.9-slim',
    api_version='auto',
    auto_remove=True,
    mount_tmp_dir=False,
    command=[
        "bash", "-c", 
        """pip install trino pandas pyarrow && 
        python -c "
import trino
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conectar ao Trino
conn = trino.dbapi.connect(
    host='trino',
    port=8080,
    user='trino',
    catalog='iceberg',
    schema='gold'
)

# Exportar features do proponente
logger.info('Exportando features do proponente...')
df_proponente = pd.read_sql('SELECT * FROM proponente_features_agro', conn)
# Adicionar timestamp se não existir, ou renomear coluna existente
if 'feature_timestamp' not in df_proponente.columns:
    if 'ultima_atualizacao' in df_proponente.columns:
        df_proponente['feature_timestamp'] = df_proponente['ultima_atualizacao']
    else:
        df_proponente['feature_timestamp'] = pd.Timestamp.now()
df_proponente.to_parquet('/feast_repo/data/gold_proponente_features.parquet', index=False)
logger.info(f'Proponente: {len(df_proponente)} registros exportados')

# Exportar features de localização  
logger.info('Exportando features de localização...')
df_location = pd.read_sql('SELECT * FROM location_features_agro', conn)
# Adicionar timestamp se não existir, ou renomear coluna existente
if 'feature_timestamp' not in df_location.columns:
    if 'ultima_atualizacao' in df_location.columns:
        df_location['feature_timestamp'] = df_location['ultima_atualizacao']
    else:
        df_location['feature_timestamp'] = pd.Timestamp.now()
df_location.to_parquet('/feast_repo/data/gold_location_features.parquet', index=False)
logger.info(f'Localização: {len(df_location)} registros exportados')

# Exportar features de risco
logger.info('Exportando features de risco...')
df_risk = pd.read_sql('SELECT * FROM risk_features_agro', conn)
# Adicionar timestamp se não existir, ou renomear coluna existente
if 'feature_timestamp' not in df_risk.columns:
    if 'ultima_atualizacao' in df_risk.columns:
        df_risk['feature_timestamp'] = df_risk['ultima_atualizacao']
    else:
        df_risk['feature_timestamp'] = pd.Timestamp.now()
df_risk.to_parquet('/feast_repo/data/gold_risk_features.parquet', index=False)
logger.info(f'Risco: {len(df_risk)} registros exportados')

logger.info('Todas as features foram exportadas com sucesso!')
"
        """
    ],
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    mounts=[
        Mount(source=str(Path(project_root) / 'feast_repo'), target='/feast_repo', type='bind')
    ],
    dag=dag,
)

# Task para otimizar tabelas Gold no Iceberg
optimize_gold_tables = DockerOperator(
    task_id='optimize_gold_tables',
    image='trinodb/trino:450',
    api_version='auto',
    auto_remove=True,
    mount_tmp_dir=False,
    command=[
        "bash", "-c",
        """echo '=== Otimizando tabelas Gold no Iceberg ===' && 
        trino --server trino:8080 --catalog iceberg --schema gold --execute "ALTER TABLE proponente_features_agro EXECUTE optimize(file_size_threshold => '50MB'); ANALYZE proponente_features_agro;" && 
        trino --server trino:8080 --catalog iceberg --schema gold --execute "ALTER TABLE location_features_agro EXECUTE optimize(file_size_threshold => '50MB'); ANALYZE location_features_agro;" && 
        trino --server trino:8080 --catalog iceberg --schema gold --execute "ALTER TABLE risk_features_agro EXECUTE optimize(file_size_threshold => '50MB'); ANALYZE risk_features_agro;" && 
        echo '=== Otimização concluída ==='"""
    ],
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    dag=dag,
)

# Task para aplicar configurações do Feast
feast_apply = DockerOperator(
    task_id='feast_apply',
    image='python:3.9-slim',
    api_version='auto',
    auto_remove=True,
    mount_tmp_dir=False,
    command=[
        "bash", "-c",
        """pip install feast[redis] && 
        cd /feast_repo && 
        echo '=== Verificando diretório e arquivos ===' && 
        ls -la && 
        echo '=== Conteúdo do feature_store.yaml ===' && 
        cat feature_store.yaml && 
        echo '=== Conteúdo do definitions.py ===' && 
        head -20 definitions.py && 
        echo '=== Aplicando configurações do Feast ===' && 
        feast apply && 
        echo '=== Verificando se registry foi criado ===' && 
        ls -la registry.db && 
        echo '=== Configurações do Feast aplicadas com sucesso ==='"""
    ],
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    mounts=[
        Mount(source=str(Path(project_root) / 'feast_repo'), target='/feast_repo', type='bind')
    ],
    environment={
        'FEAST_REGISTRY_PATH': '/feast_repo/registry.db',
        'AWS_ACCESS_KEY_ID': 'minio',
        'AWS_SECRET_ACCESS_KEY': 'minio123',
        'AWS_S3_ENDPOINT_URL': 'http://minio:9000'
    },
    dag=dag,
)

# Task para materializar features no online store (Redis)
feast_materialize = DockerOperator(
    task_id='feast_materialize',
    image='python:3.9-slim',
    api_version='auto',
    auto_remove=True,
    mount_tmp_dir=False,
    command=[
        "bash", "-c",
        """pip install feast[redis] && 
        cd /feast_repo && 
        echo '=== Verificando registry antes da materialização ===' && 
        ls -la registry.db && 
        echo '=== Verificando arquivos de dados ===' && 
        ls -la data/ && 
        echo '=== Materializando features no online store (Redis) ===' && 
        feast materialize $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) $(date -u +%Y-%m-%dT%H:%M:%S) && 
        echo '=== Features materializadas com sucesso ==='"""
    ],
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    mounts=[
        Mount(source=str(Path(project_root) / 'feast_repo'), target='/feast_repo', type='bind')
    ],
    environment={
        'FEAST_REGISTRY_PATH': '/feast_repo/registry.db',
        'AWS_ACCESS_KEY_ID': 'minio',
        'AWS_SECRET_ACCESS_KEY': 'minio123',
        'AWS_S3_ENDPOINT_URL': 'http://minio:9000'
    },
    dag=dag,
)

# Task para coletar métricas das features
collect_gold_metrics = DockerOperator(
    task_id='collect_gold_metrics',
    image='trinodb/trino:450',
    api_version='auto',
    auto_remove=True,
    mount_tmp_dir=False,
    command=[
        "bash", "-c",
        """echo '=== Coletando métricas das features Gold ===' && 
        trino --server trino:8080 --catalog iceberg --schema gold --execute "SELECT COUNT(*) as total_features FROM proponente_features_agro;" && 
        trino --server trino:8080 --catalog iceberg --schema gold --execute "SELECT COUNT(*) as total_features FROM location_features_agro;" && 
        trino --server trino:8080 --catalog iceberg --schema gold --execute "SELECT COUNT(*) as total_features FROM risk_features_agro;" && 
        echo '=== Métricas coletadas com sucesso ==='"""
    ],
    docker_url='unix://var/run/docker.sock',
    network_mode='modern-data-pipeline_data_pipeline_net',
    dag=dag,
)

# Task final
log_end = PythonOperator(
    task_id='log_end',
    python_callable=log_completion_info,
    trigger_rule='none_failed',
    dag=dag,
)

# Definição das dependências
log_start >> dbt_run_gold >> dbt_test_gold >> export_features_to_parquet >> optimize_gold_tables >> feast_apply >> feast_materialize >> collect_gold_metrics >> log_end