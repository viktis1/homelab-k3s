FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# There is no need for a listening port, since the service creates an outbound connection itself.
CMD ["python", "worker.py"] 
