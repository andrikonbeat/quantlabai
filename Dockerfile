# QuantLab AI - Docker Configuration

# ============================================================
# SQX Daemon (StrategyQuant X -gui)
# ============================================================
# Build: docker build -t quantlab/sqx:144.2953 -f Dockerfile.sqx assets/SQX_144_2953_linux_20260601/
# Run: docker run -d --name sqx-daemon -p 5050:5050 -p 5051:5051 -v ./knowledge:/opt/StrategyQuantX/user quantlab/sqx:144.2953

FROM ubuntu:22.04 AS sqx-base

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    fluxbox \
    openjdk-11-jre-headless \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxi6 \
    libxrandr2 \
    libxfixes3 \
    libxcursor1 \
    libxcomposite1 \
    libxdamage1 \
    libxinerama1 \
    libxi6 \
    libxtst6 \
    libasound2 \
    libpulse0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libxkbcommon0 \
    libxshmfence1 \
    libgtk-3-0 \
    libgdk-pixbuf-2.0-0 \
    libgconf-2-4 \
    libxss1 \
    libappindicator3-1 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libvulkan1 \
    wget \
    curl \
    ca-certificates \
    fontconfig \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install xvfb-run wrapper
RUN echo '#!/bin/bash\nxvfb-run -a -s "-screen 0 1920x1080x24" "$@"' > /usr/local/bin/xvfb-run && chmod +x /usr/local/bin/xvfb-run

# Create sqx user
RUN groupadd -r sqx && useradd -r -g sqx -d /home/sqx -s /bin/bash sqx && mkdir -p /home/sqx && chown sqx:sqx /home/sqx

WORKDIR /opt/StrategyQuantX
USER sqx

# Copy SQX installation (done at build time via COPY)
# COPY --chown=sqx:sqx . /opt/StrategyQuantX/

EXPOSE 5050 5051

# Start Xvfb and SQX
ENTRYPOINT ["/bin/bash", "-c", "Xvfb :99 -screen 0 1920x1080x24 & sleep 2 && ./StrategyQuantX -gui -port 5050"]


# ============================================================
# QuantLab API Runtime
# ============================================================
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the package via setuptools build-system (sdk/pyproject.toml)
COPY sdk/pyproject.toml ./
COPY sdk/quantlab ./quantlab
RUN pip install --no-cache-dir -e .

# Copy source data
COPY pipelines ./pipelines
COPY knowledge ./knowledge
COPY reports ./reports

# Create non-root user
RUN groupadd -r quantlab && useradd -r -g quantlab -d /app -s /bin/bash quantlab
RUN chown -R quantlab:quantlab /app
USER quantlab

ENV PATH="/home/quantlab/.local/bin:$PATH"

EXPOSE 8080

CMD ["quantlab", "api"]


# ============================================================
# QuantLab Development Image
# ============================================================
FROM base AS dev

ENV PYTHONPATH=/app

# Install dev dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    pytest-mock \
    black \
    isort \
    ruff \
    mypy \
    pre-commit

CMD ["python", "-m", "quantlab.cli", "--help"]


# ============================================================
# QuantLab Production Runtime
# ============================================================
FROM base AS runtime

ENV QUANTLAB_ENV=production

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import quantlab; print('OK')" || exit 1

CMD ["quantlab", "api"]