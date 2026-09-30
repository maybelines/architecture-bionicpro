FROM apache/airflow:2.10.5-python3.11
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==2.10.5" -r /tmp/requirements.txt
ENV AIRFLOW_HOME=/opt/airflow/state
RUN mkdir -p /opt/airflow/state
COPY dags /opt/airflow/dags
