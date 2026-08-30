FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY bot.py db.py accounting.py accounts_seed.py ./

# Persistent storage untuk SQLite database
RUN mkdir -p /var/data
ENV DB_PATH=/var/data/finance.db

# Telegram Bot Token (di-set via Render env vars)
ENV BOT_TOKEN=""

# Run
CMD ["python", "bot.py"]