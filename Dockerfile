FROM python:3.12-slim AS base

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1


# Install the virtual env
FROM base AS python-deps

RUN pip install poetry
RUN poetry config virtualenvs.in-project true

RUN apt-get update && apt-get install -y --no-install-recommends gcc

COPY pyproject.toml .
COPY poetry.lock .

RUN poetry install --without dev --no-root


# Make the app user
FROM base AS runtime

COPY --from=python-deps /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

RUN useradd --create-home appuser
WORKDIR /home/appuser

COPY . .

USER appuser

EXPOSE 8000
ENTRYPOINT [ "uvicorn" ]

CMD [ "app.app:app", "--host", "0.0.0.0", "--port", "8000" ]
