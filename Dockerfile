FROM ubuntu:latest

# Install bash and Python dependencies
RUN apt-get update && apt-get install -y \
    bash \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install FastAPI and uvicorn for HTTP API
RUN pip install fastapi uvicorn

# Create working directory
WORKDIR /app

# Copy API script
COPY api.py /app/api.py

# Expose port 8000 for MCP connection
EXPOSE 8000

# Start the API server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]