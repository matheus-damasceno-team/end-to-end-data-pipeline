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
RUN pip install \
    apache-airflow-providers-postgres \
    apache-airflow-providers-docker