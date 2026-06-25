FROM python:3.11-slim

WORKDIR /app

# Install dependencies dulu (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Port aplikasi (sesuai keputusan: 5010)
ENV APP_PORT=5010
EXPOSE 5010

# Jalankan dengan gunicorn untuk production-grade serving
RUN pip install --no-cache-dir gunicorn==22.0.0
CMD ["gunicorn", "--bind", "0.0.0.0:5010", "--workers", "2", "--timeout", "60", "app:app"]
