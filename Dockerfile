FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Each compose service overrides this with its own server, e.g.:
#   command: python 03-remote-auth/server.py
CMD ["python", "02-remote-basic/server.py"]
