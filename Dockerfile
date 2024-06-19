FROM python:3.10-slim as base

MAINTAINER David E. Weirich "weirich.david@gmail.com"

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDOCKWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1


# Install the virtual env
FROM base AS python-deps

RUN pip install poetry
RUN poetry config virtualenvs.in-project true

RUN apt-get update && apt-get install -y --no-install-recommends gcc

COPY pyproject.toml .
COPY poetry.lock .

RUN poetry install --no-dev


# Make the app user
FROM base AS runtime

COPY --from=python-deps /.venv /.venv
ENV PATH "/.venv/bin:$PATH"

RUN useradd --create-home appuser
WORKDIR /home/appuser

COPY . .
RUN sed -i "s/debug=True/debug=False/" app/app.py

USER appuser

EXPOSE 8000
ENTRYPOINT [ "uvicorn" ]

CMD [ "app.app:app", "--host", "0.0.0.0", "--port", "8000" ]
