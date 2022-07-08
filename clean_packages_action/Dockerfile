FROM python:latest
RUN pip install pip --upgrade
RUN pip install requests
WORKDIR /app
ADD clean_ghcr.py /app/clean_ghcr.py
ENTRYPOINT ["python", "/app/clean_ghcr.py"]
