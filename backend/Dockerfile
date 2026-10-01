# Build context: repository root (docker build -f backend/Dockerfile .)
FROM python:3.12-slim
WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG WITH_VOSK=1
RUN if [ "$WITH_VOSK" = "1" ]; then python -c "import io, urllib.request, zipfile; \
zipfile.ZipFile(io.BytesIO(urllib.request.urlopen('https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip').read())).extractall('/srv/models')"; fi

COPY backend/ /srv/backend/
COPY configs/ /srv/configs/
COPY data/ /srv/data/
ENV PROJECT_ROOT=/srv
RUN python scripts/make_sample_pdfs.py && python -m app.ingestion.pipeline > /dev/null
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
