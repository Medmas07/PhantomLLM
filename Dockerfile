FROM mcr.microsoft.com/playwright/python:v1.54.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PHANTOM_MODE=api \
    PHANTOM_MODEL=openai_ui \
    PHANTOM_BROWSER=camoufox \
    PHANTOM_HEADLESS=true \
    PHANTOM_HOST=0.0.0.0 \
    PHANTOM_PORT=8000

RUN useradd --create-home --uid 10001 phantom

WORKDIR /app/PhantomLLM

COPY PhantomLLM/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY PhantomLLM/ ./
COPY docker/entrypoint.sh /usr/local/bin/phantom-entrypoint.sh

RUN sed -i 's/\r$//' /usr/local/bin/phantom-entrypoint.sh && \
    chmod +x /usr/local/bin/phantom-entrypoint.sh && \
    chown -R phantom:phantom /app /usr/local/bin/phantom-entrypoint.sh

USER phantom
RUN python -m camoufox fetch

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/phantom-entrypoint.sh"]

