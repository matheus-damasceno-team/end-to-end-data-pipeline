FROM apache/airflow:2.9.3

USER root
# Instalar dependências incluindo Docker CLI
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Adicionar usuário airflow ao grupo docker
RUN groupadd -f docker && usermod -aG docker airflow

USER airflow
# Instalar providers necessários
RUN pip install --no-cache-dir \
    apache-airflow-providers-postgres \
    apache-airflow-providers-docker \
    apache-airflow-providers-http

# Instalar dependências científicas com versões compatíveis
RUN pip install --no-cache-dir \
    pandas \
    numpy \
    scikit-learn \
    redis \
    trino \
    scipy \
    requests