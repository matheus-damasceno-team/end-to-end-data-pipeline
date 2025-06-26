# Dockerfile for feast-serve service

FROM python:3.9-slim-bookworm

LABEL maintainer="jules-ai"
LABEL description="Feast serving image with necessary build tools and dependencies."

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    FEAST_USAGE="False"

# Set working directory
WORKDIR /app

# Install system dependencies including build tools
# build-essential includes gcc, g++, make, etc.
# python3-dev provides Python.h and other headers needed for compiling C extensions.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy the local feast repository content into the image
# This assumes your feature_store.yaml and definitions.py are in a directory
# that will be provided as the build context for this Dockerfile.
# In docker-compose.yml, the build context for feast-serve will be ./services/feast_serve
# So, we need to copy from a path relative to that, or mount feast_repo as a volume.
# For a cleaner image build, it's often better to COPY the necessary repo files.
# However, the current setup mounts `./feast_repo:/app/feast_repo` in docker-compose.
# Let's assume the feast_repo will be mounted, so we don't COPY it here.
# If we were to COPY, it would be:
# COPY ../../feast_repo ./feast_repo
# WORKDIR /app/feast_repo

# Install Python dependencies
# Using a requirements.txt file is often cleaner, but for this direct translation:
RUN pip install --no-cache-dir feast[aws]==0.37.1 boto3

# Expose the Feast gRPC port (default is 6566)
EXPOSE 6566

# Define the command to run Feast server
# This will be the default command if docker-compose doesn't override it.
# The working directory for this command should be where feature_store.yaml is.
# If feast_repo is mounted to /app/feast_repo, then WORKDIR /app/feast_repo is needed.
# Let's adjust WORKDIR to /app/feast_repo to match the volume mount expectation.
WORKDIR /app/feast_repo

# Command to start feast server.
# This assumes feature_store.yaml is in /app/feast_repo (current WORKDIR).
CMD ["feast", "serve", "--host", "0.0.0.0", "--port", "6566"]

# Notes:
# - The base image python:3.9-slim-bookworm is Debian Bookworm based.
# - build-essential should provide gcc and g++.
# - python3-dev is crucial for compiling Python C extensions.
# - The feast_repo content (feature_store.yaml, definitions.py) is expected to be
#   mounted via docker-compose.yml into /app/feast_repo.
#   If not, these files would need to be COPY'd into the image.
# - FEAST_USAGE is set to False via ENV. Other env vars like AWS creds
#   will be passed by docker-compose.yml.
# - The CMD starts feast serve. The docker-compose.yml will likely override
#   this CMD if it has its own `command:` field, but it's good practice to have a default.
#   The new plan is to remove the complex `command` from docker-compose.yml.
# - The WORKDIR is set to /app/feast_repo, so `feast serve` will look for `feature_store.yaml` there.
#   The volume mount in docker-compose.yml is `./feast_repo:/app/feast_repo`. This aligns.
