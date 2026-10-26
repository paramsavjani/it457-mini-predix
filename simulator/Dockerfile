# The simulator uses only the Python standard library, so no pip install.
FROM python:3.12-alpine

ENV PYTHONUNBUFFERED=1
WORKDIR /srv
COPY simulator.py .

RUN adduser -D predix
USER predix

CMD ["python", "simulator.py"]
