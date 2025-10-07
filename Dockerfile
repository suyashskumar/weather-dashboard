# Use your prebuilt base image from ECR (replace ACCOUNT_ID with yours)
FROM 491519648367.dkr.ecr.us-east-1.amazonaws.com/weather-base:latest

# Set working directory
WORKDIR /app

# Copy the rest of your app (source code, static files, etc.)
COPY . .

# Prevent Python output buffering (for cleaner logs)
ENV PYTHONUNBUFFERED=1

# Expose Flask/Gunicorn port
EXPOSE 5000

# Run the app with Gunicorn (production server)
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
