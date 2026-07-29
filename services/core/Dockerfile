# Multi-stage build. The builder stage owns the C++ toolchain (pickpath-native
# is compiled here via scikit-build-core/pybind11); runtime stages copy the
# finished virtualenv and stay slim.
FROM python:3.13-slim AS builder
ENV PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY services/core/requirements/ /tmp/requirements/
RUN pip install -r /tmp/requirements/prod.txt
COPY native/ /tmp/native/
RUN pip install /tmp/native/pickpath /tmp/native/pickpath-native

FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY services/core/ /app/
COPY native/bench_pickpath.py /opt/bench_pickpath.py
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
EXPOSE 8000

FROM base AS dev
COPY services/core/requirements/ /tmp/requirements/
RUN pip install -r /tmp/requirements/dev.txt
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS prod
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY=build-time-only python manage.py collectstatic --no-input
RUN useradd --create-home appuser
USER appuser
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
