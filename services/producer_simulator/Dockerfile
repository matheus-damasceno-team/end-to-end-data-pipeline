# Dockerfile for Kafka Avro Producer Simulator

FROM python:3.9-slim

WORKDIR /app

# Install required Python libraries
RUN pip install --no-cache-dir confluent-kafka avro-python3

COPY producer.py .
COPY producer_schema.avsc .

CMD ["python", "producer.py"]