from datetime import timedelta

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.sensors.filesystem import FileSensor
from airflow.utils.dates import days_ago

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['your_email@example.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'pssm_gremlin_processing',
    default_args=default_args,
    description='A DAG to process PSSM GREMLIN tasks',
    schedule_interval=timedelta(days=1),
    start_date=days_ago(1),
    tags=['bioinformatics'],
)

# Assuming files are uploaded to a specific directory
file_sensor_task = FileSensor(
    task_id='file_sensor',
    filepath='/path/to/uploaded/files/*.fasta',
    fs_conn_id='fs_default',
    poke_interval=300,
    timeout=600,
    dag=dag,
)


def validate_file(file_path):
    # Code to validate the file
    pass


validate_file_task = PythonOperator(
    task_id='validate_file',
    python_callable=validate_file,
    op_kwargs={'file_path': '{{ ti.xcom_pull(task_ids="file_sensor") }}'},
    dag=dag,
)


def process_file(file_path):
    # Code to process the file
    pass


process_file_task = PythonOperator(
    task_id='process_file',
    python_callable=process_file,
    op_kwargs={'file_path': '{{ ti.xcom_pull(task_ids="validate_file") }}'},
    dag=dag,
)


def compile_results(md5sum):
    # Code to compile results
    pass


compile_results_task = PythonOperator(
    task_id='compile_results',
    python_callable=compile_results,
    op_kwargs={'md5sum': '{{ ti.xcom_pull(task_ids="process_file") }}'},
    dag=dag,
)

# Setting up the task sequence
file_sensor_task >> validate_file_task >> process_file_task >> compile_results_task
