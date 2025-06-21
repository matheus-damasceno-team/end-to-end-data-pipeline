# Producer Simulator Dockerfile
# PATH: services/producer_simulator/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the producer
CMD ["python", "producer.py"]