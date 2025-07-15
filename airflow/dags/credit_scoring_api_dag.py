from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import logging

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 7, 7),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'credit_scoring_api_host',
    default_args=default_args,
    description='Host Credit Scoring API for real-time predictions',
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=['api', 'credit-scoring', 'ml-serving']
)

def check_dependencies():
    import redis
    import requests
    
    try:
        redis_client = redis.Redis(host='redis', port=6379, db=0)
        redis_client.ping()
        logger.info("Redis connection OK")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise
    
    try:
        response = requests.get('http://trino:8080/ui/')
        if response.status_code == 200:
            logger.info("Trino connection OK")
    except Exception as e:
        logger.error(f"Trino connection failed: {e}")
        raise

check_dependencies_task = PythonOperator(
    task_id='check_dependencies',
    python_callable=check_dependencies,
    dag=dag
)

build_and_start_api = BashOperator(
    task_id='build_and_start_api',
    bash_command='''
    cd /opt/airflow/services/credit_scoring_api
    docker build -t credit-scoring-api:latest .
    docker stop credit-scoring-api || true
    docker rm credit-scoring-api || true
    docker run -d \
        --name credit-scoring-api \
        --network modern-data-pipeline_data_pipeline_net \
        -p 8087:8000 \
        -e REDIS_HOST=redis \
        -e REDIS_PORT=6379 \
        -e TRINO_HOST=trino \
        -e TRINO_PORT=8080 \
        -v $PROJECT_ROOT/services/credit_scoring_api/models:/app/models \
        credit-scoring-api:latest
    ''',
    dag=dag
)

check_dependencies_task >> build_and_start_api

if __name__ == "__main__":
    dag.cli()