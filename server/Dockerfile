FROM python:3.11
WORKDIR /server
COPY requirements.txt /server
RUN pip3 install -r requirements.txt --no-cache-dir
COPY server.py /server
CMD ["python3", "server.py"]
