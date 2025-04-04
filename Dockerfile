FROM python:3.10-slim
RUN apt-get update && apt-get install -y ffmpeg
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["/bin/sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120"]
