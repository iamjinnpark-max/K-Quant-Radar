FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

RUN groupadd --system kquant \
    && useradd --system --gid kquant --no-create-home kquant

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY --chown=kquant:kquant backend/app /app/platform_api
COPY --chown=kquant:kquant backend/alembic /app/alembic
COPY --chown=kquant:kquant backend/alembic.ini /app/alembic.ini
COPY --chown=kquant:kquant features.py financials.py fundamentals.py \
    investor_flow.py model.py news_sentiment.py options_signals.py \
    personalization.py regime.py screener.py stock_universe.py utils.py /app/

RUN chmod -R a-w /app

USER kquant
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "platform_api.main:app", "--host=0.0.0.0", "--port=8000"]
