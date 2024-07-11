# syntax=docker/dockerfile:1
FROM cnstark/pytorch:2.0.1-py3.10.11-ubuntu22.04
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "clip_server.py"]
