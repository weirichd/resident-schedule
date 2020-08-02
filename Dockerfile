FROM python:3.7-slim as base

MAINTAINER David E. Weirich "weirich.david@gmail.com"

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDOCKWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1


FROM base AS python-deps

RUN pip install pipenv
RUN apt-get update && apt-get install -y --no-install-recommends gcc

COPY Pipfile .
COPY Pipfile.lock .

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy


FROM base AS runtime

COPY --from=python-deps /.venv /.venv
ENV PATH "/.venv/bin:$PATH"

RUN useradd --create-home appuser
WORKDIR /home/appuser
USER appuser

COPY . .

EXPOSE 8000
ENTRYPOINT [ "python" ]

CMD [ "application.py" ]
