# syntax=docker/dockerfile:1
FROM huggingface/transformers-pytorch-cpu
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "clip_server.py"]
