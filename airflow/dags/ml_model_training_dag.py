from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler
import joblib
import logging
import os
import trino
import redis
import json
from scipy import stats

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'ml-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 7, 7),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'ml_model_training_pipeline',
    default_args=default_args,
    description='ML Model Training, Testing, and Retraining Pipeline',
    schedule_interval=timedelta(hours=6),
    catchup=False,
    max_active_runs=1,
    tags=['ml', 'training', 'data-drift', 'model-management']
)

def extract_features_from_gold_layer():
    logger.info("Extracting features from Gold layer")
    
    conn = trino.dbapi.connect(
        host='trino',
        port=8080,
        user='airflow',
        catalog='iceberg',
        schema='gold'
    )
    
    # Simplified query - just get proponente features for now
    query = """
    SELECT 
        proponente_id,
        total_solicitacoes,
        valor_total_solicitado,
        valor_medio_solicitado,
        valor_maximo_solicitado,
        valor_minimo_solicitado,
        serasa_score_medio,
        anos_experiencia_medio,
        area_media_hectares,
        taxa_autuacoes_ibama,
        diversidade_culturas,
        diversidade_finalidades
    FROM proponente_features_agro
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    logger.info(f"Extracted {len(df)} records from Gold layer")
    return df

def create_target_variable(df):
    logger.info("Creating target variable for supervised learning")
    
    np.random.seed(42)
    
    # Fill NaN values with safe defaults
    df = df.fillna({
        'valor_total_solicitado': df['valor_total_solicitado'].median() if not df['valor_total_solicitado'].isna().all() else 50000,
        'anos_experiencia_medio': df['anos_experiencia_medio'].median() if not df['anos_experiencia_medio'].isna().all() else 10,
        'serasa_score_medio': df['serasa_score_medio'].median() if not df['serasa_score_medio'].isna().all() else 600,
        'area_media_hectares': df['area_media_hectares'].median() if not df['area_media_hectares'].isna().all() else 100,
        'taxa_autuacoes_ibama': 0,
        'diversidade_culturas': 1
    })
    
    base_prob = 0.3
    
    # Simplified and safer scoring
    valor_norm = np.clip(df['valor_total_solicitado'] / 200000, 0, 2)  # normalize to 0-2
    exp_norm = np.clip(df['anos_experiencia_medio'] / 30, 0, 2)  # normalize to 0-2
    serasa_norm = np.clip(df['serasa_score_medio'] / 900, 0, 1)  # normalize to 0-1
    area_norm = np.clip(df['area_media_hectares'] / 1000, 0, 2)  # normalize to 0-2
    
    # Conservative adjustments
    prob_adjustments = (
        (valor_norm - 1) * 0.05 +  # larger requests = slightly higher risk
        (1 - exp_norm) * 0.1 +     # less experience = higher risk
        (serasa_norm - 0.5) * 0.2 + # score above/below 450 affects risk
        (area_norm - 1) * 0.03     # larger area = slightly lower risk
    )
    
    # Ensure probabilities are valid
    default_probabilities = np.clip(base_prob + prob_adjustments, 0.1, 0.9)
    
    # Check for any remaining invalid values
    if np.any(np.isnan(default_probabilities)) or np.any(default_probabilities < 0) or np.any(default_probabilities > 1):
        logger.warning("Invalid probabilities detected, using base probability")
        default_probabilities = np.full(len(df), base_prob)
    
    df['target_default'] = np.random.binomial(1, default_probabilities)
    
    logger.info(f"Created target variable with default rate: {df['target_default'].mean():.3f}")
    return df

def detect_data_drift(**context):
    logger.info("Detecting data drift in new data")
    
    current_data = extract_features_from_gold_layer()
    
    try:
        historical_data = pd.read_pickle('/tmp/historical_data.pkl')
        logger.info(f"Loaded historical data with {len(historical_data)} records")
    except FileNotFoundError:
        logger.info("No historical data found, saving current data as baseline")
        current_data.to_pickle('/tmp/historical_data.pkl')
        return False
    
    drift_detected = False
    drift_features = []
    
    numerical_features = ['valor_total_solicitado', 'valor_medio_solicitado', 
                         'area_media_hectares', 'anos_experiencia_medio', 'serasa_score_medio']
    
    for feature in numerical_features:
        if feature in current_data.columns and feature in historical_data.columns:
            current_dist = current_data[feature].dropna()
            historical_dist = historical_data[feature].dropna()
            
            if len(current_dist) > 30 and len(historical_dist) > 30:
                statistic, p_value = stats.ks_2samp(current_dist, historical_dist)
                
                if p_value < 0.05:
                    drift_detected = True
                    drift_features.append(feature)
                    logger.warning(f"Data drift detected in {feature}: p-value = {p_value:.4f}")
    
    if drift_detected:
        logger.warning(f"Data drift detected in features: {drift_features}")
        context['task_instance'].xcom_push(key='drift_detected', value=True)
        context['task_instance'].xcom_push(key='drift_features', value=drift_features)
    else:
        logger.info("No significant data drift detected")
        context['task_instance'].xcom_push(key='drift_detected', value=False)
    
    return drift_detected

def train_model(**context):
    logger.info("Training ML model")
    
    df = extract_features_from_gold_layer()
    df_with_target = create_target_variable(df)
    
    feature_columns = [
        'total_solicitacoes', 'valor_total_solicitado', 'valor_medio_solicitado',
        'valor_maximo_solicitado', 'valor_minimo_solicitado', 'serasa_score_medio',
        'anos_experiencia_medio', 'area_media_hectares', 'taxa_autuacoes_ibama',
        'diversidade_culturas', 'diversidade_finalidades'
    ]
    
    X = df_with_target[feature_columns].fillna(0)
    y = df_with_target['target_default']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train_scaled, y_train)
    
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average='weighted')
    recall = recall_score(y_test, y_pred, average='weighted')
    f1 = f1_score(y_test, y_pred, average='weighted')
    
    logger.info(f"Model performance - Accuracy: {accuracy:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1:.4f}")
    
    model_package = {
        'model': model,
        'scaler': scaler,
        'feature_columns': feature_columns,
        'metrics': {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1
        },
        'training_date': datetime.now().isoformat()
    }
    
    # Save model directly to shared directory that's accessible by both Airflow and API
    model_dir = '/opt/airflow/shared_models'
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = f'{model_dir}/credit_model.joblib'
    joblib.dump(model_package, model_path)
    
    # Also save metrics separately for easy access
    metrics_path = f'{model_dir}/model_metrics.json'
    with open(metrics_path, 'w') as f:
        json.dump(model_package['metrics'], f, indent=2)
    
    logger.info(f"Model saved successfully to {model_path}")
    logger.info(f"Metrics saved to {metrics_path}")
    logger.info(f"Model will be accessible by API at /app/models/")
    
    context['task_instance'].xcom_push(key='model_metrics', value=model_package['metrics'])
    
    return model_package['metrics']

def evaluate_model_performance(**context):
    logger.info("Evaluating model performance")
    
    current_metrics = context['task_instance'].xcom_pull(task_ids='train_model', key='model_metrics')
    
    # Use the same directory where models are saved
    metrics_dir = '/opt/airflow/shared_models'
    previous_metrics_file = f'{metrics_dir}/previous_model_metrics.json'
    
    try:
        with open(previous_metrics_file, 'r') as f:
            previous_metrics = json.load(f)
        
        performance_degraded = (
            current_metrics['accuracy'] < previous_metrics['accuracy'] - 0.05 or
            current_metrics['f1'] < previous_metrics['f1'] - 0.05
        )
        
        if performance_degraded:
            logger.warning("Model performance degraded compared to previous version")
            logger.info(f"Current: Accuracy={current_metrics['accuracy']:.4f}, F1={current_metrics['f1']:.4f}")
            logger.info(f"Previous: Accuracy={previous_metrics['accuracy']:.4f}, F1={previous_metrics['f1']:.4f}")
        else:
            logger.info("Model performance is acceptable")
            
    except FileNotFoundError:
        logger.info("No previous model metrics found")
        performance_degraded = False
    
    # Save current metrics as previous for next run
    os.makedirs(metrics_dir, exist_ok=True)
    with open(previous_metrics_file, 'w') as f:
        json.dump(current_metrics, f, indent=2)
    
    context['task_instance'].xcom_push(key='performance_degraded', value=performance_degraded)
    
    logger.info(f"Current model metrics: {current_metrics}")
    return current_metrics

def deploy_model(**context):
    logger.info("Deploying model")
    
    try:
        drift_detected = context['task_instance'].xcom_pull(task_ids='detect_data_drift', key='drift_detected') or False
        performance_degraded = context['task_instance'].xcom_pull(task_ids='evaluate_model_performance', key='performance_degraded') or False
        
        if drift_detected or performance_degraded:
            logger.info("Deploying new model due to drift or performance issues")
            deploy_decision = True
        else:
            logger.info("No deployment needed - model is current")
            deploy_decision = False
        
        if deploy_decision:
            try:
                deploy_path = '/opt/airflow/shared_models'
                model_file = f'{deploy_path}/credit_model.joblib'
                metrics_file = f'{deploy_path}/model_metrics.json'
                
                if os.path.exists(model_file):
                    logger.info(f"Model already deployed at {model_file}")
                    logger.info(f"Metrics available at {metrics_file}")
                    
                    # Create a deployment timestamp file
                    deployment_info = {
                        'deployed_at': datetime.now().isoformat(),
                        'model_file': 'credit_model.joblib',
                        'metrics_file': 'model_metrics.json',
                        'drift_detected': drift_detected,
                        'performance_degraded': performance_degraded
                    }
                    
                    deployment_file = f'{deploy_path}/deployment_info.json'
                    with open(deployment_file, 'w') as f:
                        json.dump(deployment_info, f, indent=2)
                    
                    logger.info(f"Deployment info saved to {deployment_file}")
                else:
                    logger.warning(f"Model file not found at {model_file}, deployment may have failed")
            except Exception as e:
                logger.error(f"Error in deployment verification: {e}")
                # Não falhar a DAG por problemas de deployment
        
        return deploy_decision
    except Exception as e:
        logger.error(f"Error in deploy_model: {e}")
        return False

def update_model_registry(**context):
    logger.info("Updating model registry")
    
    try:
        import redis
        import json
        
        redis_client = redis.Redis(host='redis', port=6379, db=1, decode_responses=True)
        
        # Test connection
        redis_client.ping()
        
        model_info = {
            'model_version': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'training_date': datetime.now().isoformat(),
            'metrics': context['task_instance'].xcom_pull(task_ids='train_model', key='model_metrics') or {},
            'drift_detected': context['task_instance'].xcom_pull(task_ids='detect_data_drift', key='drift_detected') or False,
            'deployed': context['task_instance'].xcom_pull(task_ids='deploy_model') or False
        }
        
        redis_client.setex('latest_model_info', 86400, json.dumps(model_info))
        
        logger.info(f"Model registry updated with version: {model_info['model_version']}")
        
        return model_info
        
    except Exception as e:
        logger.error(f"Error updating model registry: {e}")
        # Don't fail the DAG for registry issues
        return {
            'model_version': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'training_date': datetime.now().isoformat(),
            'status': 'registry_error'
        }

def check_data_availability():
    """Verifica se há dados disponíveis nas tabelas Gold"""
    import trino
    
    logger.info("Verificando disponibilidade de dados nas tabelas Gold")
    
    conn = trino.dbapi.connect(
        host='trino',
        port=8080,
        user='airflow',
        catalog='iceberg',
        schema='gold'
    )
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM proponente_features_agro")
    count = cursor.fetchone()[0]
    
    logger.info(f"Encontrados {count} registros na tabela proponente_features_agro")
    
    if count == 0:
        raise ValueError("Nenhum dado encontrado nas tabelas Gold")
    
    conn.close()
    return count

data_availability_check = PythonOperator(
    task_id='check_data_availability',
    python_callable=check_data_availability,
    dag=dag
)

detect_drift_task = PythonOperator(
    task_id='detect_data_drift',
    python_callable=detect_data_drift,
    dag=dag
)

train_model_task = PythonOperator(
    task_id='train_model',
    python_callable=train_model,
    dag=dag
)

evaluate_model_task = PythonOperator(
    task_id='evaluate_model_performance',
    python_callable=evaluate_model_performance,
    dag=dag
)

deploy_model_task = PythonOperator(
    task_id='deploy_model',
    python_callable=deploy_model,
    dag=dag
)

update_registry_task = PythonOperator(
    task_id='update_model_registry',
    python_callable=update_model_registry,
    dag=dag
)

restart_api_task = BashOperator(
    task_id='restart_api_service',
    bash_command='''
    echo "Checking if credit-scoring-api container exists..."
    if docker ps -a | grep -q "credit-scoring-api"; then
        echo "Restarting credit-scoring-api container..."
        docker restart credit-scoring-api
        echo "API service restarted successfully"
    else
        echo "credit-scoring-api container not found, skipping restart"
    fi
    ''',
    dag=dag
)

data_availability_check >> detect_drift_task >> train_model_task >> evaluate_model_task >> deploy_model_task >> update_registry_task >> restart_api_task

if __name__ == "__main__":
    dag.cli()