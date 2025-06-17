FROM python:3.11.13

# Set working directory
WORKDIR /app

# Install curl to fetch uv
RUN apt-get update && apt-get install -y curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get purge -y curl && rm -rf /var/lib/apt/lists/*

# Add uv to path
ENV PATH="/root/.local/bin:$PATH"

# ✅ Add PYTHONPATH to find app.api
ENV PYTHONPATH="/app"

COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml
COPY . .

# Expose FastAPI and Streamlit ports
EXPOSE 8000 8501

# Start both services
CMD ["supervisord", "-c", "/app/supervisord.conf"]
