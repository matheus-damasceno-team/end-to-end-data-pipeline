FROM apache/airflow:2.9.3

USER root
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install apache-airflow-providers-postgres