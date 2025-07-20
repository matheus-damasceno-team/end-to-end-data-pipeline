from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
import logging

logger = logging.getLogger(__name__)

# Default arguments for the DAG
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    'streamlit_web_monitoring',
    default_args=default_args,
    description='Deploy and manage Streamlit web application for credit scoring',
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=['streamlit', 'web-monitoring', 'credit-scoring'],
    params={
        'reset': False  # Boolean parameter to force full deployment with prune
    }
)

build_and_start_streamlit = BashOperator(
    task_id='build_and_start_streamlit',
    bash_command='''
    cd /opt/airflow/services/streamlit_app
    
    # Check if reset flag is true
    if [ "{{ dag_run.conf.get('reset', False) }}" = "True" ]; then
        echo "RESET FLAG DETECTED - Performing complete rebuild with prune..."
        docker system prune -f
        docker build --no-cache -t streamlit-app:latest .
    else
        echo "Building Streamlit image (using cache)..."
        docker build -t streamlit-app:latest .
    fi
    
    # Stop and remove existing containers
    docker stop credit-scoring-streamlit || true
    docker rm credit-scoring-streamlit || true
    
    # Start container
    docker run -d \
        --name credit-scoring-streamlit \
        --network modern-data-pipeline_data_pipeline_net \
        -p 8501:8501 \
        -e STREAMLIT_SERVER_PORT=8501 \
        -e STREAMLIT_SERVER_HEADLESS=true \
        -e STREAMLIT_SERVER_ENABLE_CORS=false \
        -e STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
        -e STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
        -v $PROJECT_ROOT/services/streamlit_app/logs:/app/logs \
        streamlit-app:latest
    ''',
    dag=dag
)
# Task dependencies
build_and_start_streamlit
