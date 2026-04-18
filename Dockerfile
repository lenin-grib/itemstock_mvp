FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
  build-essential \
  curl \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY parser.py .
COPY forecast.py .
COPY ideal_stock.py .
COPY order_service.py .
COPY orders_tab_controller.py .
COPY orders_view_service.py .
COPY params_tab_controller.py .
COPY sales_tab_controller.py .
COPY sales_view_service.py .
COPY suppliers_tab_controller.py .
COPY suppliers_view_service.py .
COPY supplier_service.py .
COPY cache_service.py .
COPY database.py .
COPY db_utils.py .
COPY forecast_schema.py .
COPY ui_helpers.py .

# Create directory for SQLite database
RUN mkdir -p /app/data

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
