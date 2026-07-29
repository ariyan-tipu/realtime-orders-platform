FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY services/realtime/requirements.txt services/realtime/requirements-dev.txt /tmp/
RUN pip install -r /tmp/requirements.txt
COPY services/realtime/ /app/
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

FROM base AS dev
RUN pip install -r /tmp/requirements-dev.txt

FROM base AS prod
RUN useradd --create-home appuser
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers"]
