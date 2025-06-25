# Dockerfile for Kafka Consumer to MinIO

FROM python:3.9-slim

WORKDIR /app

# Install required Python libraries
RUN pip install --no-cache-dir kafka-python minio

COPY consumer.py .

# Add a small wait at startup, can also be handled in script or with docker-compose healthchecks/depends_on conditions
# CMD ["sh", "-c", "sleep 15 && python consumer.py"]
CMD ["python", "consumer.py"]
