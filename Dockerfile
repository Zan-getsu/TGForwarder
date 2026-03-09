FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY telegram_forwarder.py .
COPY generate_session.py .

# Session files will be stored in /app/sessions via volume mount
VOLUME ["/app/sessions"]

ENTRYPOINT ["python", "telegram_forwarder.py"]
