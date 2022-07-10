FROM python:3.9-alpine
RUN pip install requests==2.28.1
WORKDIR /app
COPY clean_ghcr.py /app/clean_ghcr.py
ENTRYPOINT ["python", "/app/clean_ghcr.py"]
