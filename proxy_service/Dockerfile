FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY proxy_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy proxy service code
COPY proxy_service/ ./proxy_service/

# Environment variables
ENV PYTHONPATH=/app
ENV PROXY_HOST=0.0.0.0
ENV PROXY_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "proxy_service.app:app", "--host", "0.0.0.0", "--port", "8000"]

