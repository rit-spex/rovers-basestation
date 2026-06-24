# Use Python 3.11 image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (commented out until necessary)
RUN apt-get update  \
    && apt-get install -y --no-install-recommends build-essential

# Install Python dependencies
COPY requirements.txt requirements-dev.txt /app/
RUN pip install --no-cache-dir --upgrade pip  \
    && pip install --no-cache-dir -r requirements-dev.txt

# Copy entire project directory into the image.
COPY . /app

# Default command can be overridden in docker-compose.yml
# For example, to start the API server with reload for development.
CMD ["python" "-m" "xbee.app"]
