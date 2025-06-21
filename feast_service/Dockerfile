# Custom Feast Service Dockerfile
# PATH: feast_service/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Feast and dependencies
RUN pip install --no-cache-dir \
    feast[redis]==0.32.0 \
    boto3==1.34.0 \
    requests==2.31.0

# Create feature repo directory
RUN mkdir -p /feature_repo

# Copy startup script
COPY start_feast.sh /app/start_feast.sh
RUN chmod +x /app/start_feast.sh

# Expose port
EXPOSE 6566

# Set working directory
WORKDIR /feature_repo

# Start Feast
CMD ["/app/start_feast.sh"]