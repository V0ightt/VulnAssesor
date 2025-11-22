# Use the official Python image
FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /app

# Install system dependencies (for psycopg2, wget for Nuclei installation)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        git \
        libpq-dev \
        postgresql-client \
        wget \
        unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Nuclei
RUN wget -q https://github.com/projectdiscovery/nuclei/releases/download/v3.4.10/nuclei_3.4.10_linux_amd64.zip -O nuclei.zip \
    && unzip nuclei.zip \
    && mv nuclei /usr/local/bin/ \
    && chmod +x /usr/local/bin/nuclei \
    && rm nuclei.zip \
    && nuclei -update-templates

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project code into the container
COPY . .

# Make wait-for-db helper executable
COPY wait-for-db.sh /usr/local/bin/wait-for-db.sh
RUN chmod +x wait-for-db.sh

# Expose the port Django runs on
EXPOSE 8000