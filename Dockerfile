FROM python:3.11-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV API_KEY="your-api-key-change-in-production"
ENV SECRET_KEY="your-secret-key-change-in-production"
ENV TEST_MODE="false"

EXPOSE 8000

CMD ["uvicorn", "lift_bot_api:app", "--host", "0.0.0.0", "--port", "8000"]
