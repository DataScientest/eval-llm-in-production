FROM python:3.11-slim

WORKDIR /app

# Copy and install main requirements
COPY src/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install test requirements
COPY test-requirements.txt .
RUN pip install --no-cache-dir -r test-requirements.txt

# Copy application code
COPY src/api/ .

# Copy tests directory
COPY tests/ ./tests/


EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
