# Use a lightweight official Python image
FROM python:3.10-slim

# Set environment variables to prevent .pyc files and enable stdout buffering
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install required system dependencies (e.g. for SSL certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Copy the entire local project into the container
COPY . /app

# Copy the example file to its right Name so the first run does not download one
COPY config.yaml.example /app/config.yaml

# Install the current project (assumes pyproject.toml or setup.py is present)
RUN pip install .

# Set default command (replace with your CLI tool's name if different)
ENTRYPOINT ["mqtfy"]