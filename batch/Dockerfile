FROM python:3.13.1-slim

ARG PYTHON_ENV

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python", "o1_autotrade.py"]
CMD ["local"]