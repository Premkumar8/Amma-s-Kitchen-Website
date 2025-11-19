# 1. Use the official Python 3.13.5 image as the base
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the dependency list first (for better caching)
COPY requirements.txt .

# 4. Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your application code
COPY . .

# 6. Tell Docker that this app listens on port 5000
EXPOSE 5000

# 7. The command to run your app when the container starts
CMD ["python", "app.py"]