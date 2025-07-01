FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    dbt-core==1.7.0 \
    dbt-trino==1.7.0 \
    protobuf==3.20.3

WORKDIR /dbt
ENV DBT_PROFILES_DIR=/dbt

CMD ["dbt", "run"]
