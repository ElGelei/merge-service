FROM python:3.10-slim

# Install system dependencies: ffmpeg and supervisor
RUN apt-get update && apt-get install -y ffmpeg supervisor

# Set the working directory
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy your project files into the container
COPY . /app

# Copy your Supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose the port (Render sets the $PORT variable automatically)
EXPOSE $PORT

# Start Supervisor to launch both Gunicorn and Celery
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
