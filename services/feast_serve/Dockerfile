# Use a specific Python version for reproducibility, matching other services.
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV FEAST_USAGE=False
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies and Feast
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "feast[redis,aws]==0.37.1"

# Expose the gRPC port for the feature server
EXPOSE 6566
# Expose the REST port (optional, depends on Feast version and config)
EXPOSE 6565

# The command to run the Feast server.
# This will be started in the /app/feast_repo directory (mounted as a volume).
CMD ["feast", "serve", "--host", "0.0.0.0", "--port", "6566"]