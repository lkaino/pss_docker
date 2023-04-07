FROM python:3.8-slim-buster

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY ./ /app

ENV PYTHONUNBUFFERED=0

ENTRYPOINT [ "python3", "-u", "main.py"]
