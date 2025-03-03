FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies and Poetry
# Group system-level dependencies in a single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir poetry==1.8.5

# Copy dependency files only
COPY pyproject.toml poetry.lock* ./

# Configure Poetry and install dependencies
# This layer will only be rebuilt if dependencies change
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

# Copy application code (changes frequently)
# This step is isolated so previous layers can be cached
COPY . .

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Expose port for the application
EXPOSE 8000

# Run the application with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
