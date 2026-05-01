# Use official Python base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy files into the container
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose Flask's port
EXPOSE 5000

# Run the app
CMD ["python", "app.py"]
