# Dockerfile for Kafka Producer Simulator

FROM python:3.9-slim

WORKDIR /app

# Install kafka-python library
RUN pip install --no-cache-dir kafka-python

COPY producer.py .

# Add a small wait at startup, can also be handled in script or with docker-compose healthchecks/depends_on conditions
# CMD ["sh", "-c", "sleep 10 && python producer.py"]
CMD ["python", "producer.py"]
