FROM python:3.10 as builder

WORKDIR /app

RUN pip install poetry

RUN python -m venv /venv

COPY poetry.lock pyproject.toml /app/

RUN poetry export --without-hashes -f requirements.txt | /venv/bin/pip install -r /dev/stdin

COPY . . 

RUN poetry build && /venv/bin/pip install dist/*.whl

FROM python:3.10.9-slim-bullseye

RUN apt-get update && apt-get install -y procps && rm -rf /var/lib/apt/lists/*

COPY --from=builder /venv /venv

ENV PATH="/venv/bin:${PATH}"