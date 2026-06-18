FROM python:3.12-slim

WORKDIR /app

COPY apps/x_native_api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY apps/x_native_api/*.py /app/

EXPOSE 3101
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3101"]
