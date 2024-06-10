# syntax=docker/dockerfile:1
FROM anibali/pytorch:2.0.1-nocuda
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "clip_server.py"]
