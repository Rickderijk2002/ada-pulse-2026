# Using python 3.12.7 slim image as the base image
FROM python:3.12.7-slim
# Defining working directory and copy the requirements file
WORKDIR /usr/src/myapp
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["python3","app.py"]