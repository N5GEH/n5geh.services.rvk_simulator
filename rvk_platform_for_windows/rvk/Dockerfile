FROM python:3.6.8-alpine3.9

COPY rvk/app /opt/rvk

RUN pip install -r /opt/rvk/requirements.txt

ENTRYPOINT ["python", "/opt/rvk/upload.py"]
