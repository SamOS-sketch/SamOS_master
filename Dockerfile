FROM python:3.12-slim

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Install package
RUN pip install --no-cache-dir .

# Default envs (can override at runtime)
ENV SAMOS_PERSONA=demo
ENV IMAGE_PROVIDER=stub

EXPOSE 8000
CMD ["samos", "run", "--persona", "demo"]
