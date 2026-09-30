import os
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

import clickhouse_connect
import pendulum
import psycopg2
from airflow.decorators import dag, task
from airflow.operators.python import get_current_context


def clickhouse():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
        database="bionicpro",
    )


def copy_rows(client, dsn, query, parameters, table, columns, run_id):
    # Читаем источники порциями, не передаём телеметрию через XCom.
    connection = psycopg2.connect(dsn)
    try:
        with connection.cursor(name="export_rows") as cursor:
            cursor.execute(query, parameters)
            while rows := cursor.fetchmany(5000):
                client.insert(table, [(run_id, *row) for row in rows], column_names=columns)
    finally:
        connection.close()


@dag(
    dag_id="prepare_reports",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule="0 0 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
)
def prepare_reports():
    @task
    def load_sources():
        context = get_current_context()
        configured_date = context["dag_run"].conf.get("report_date")
        report_date = (
            date.fromisoformat(configured_date)
            if configured_date
            else context["data_interval_start"].date()
        )
        if report_date >= datetime.now(timezone.utc).date():
            raise ValueError("Можно обработать только завершённый день UTC")
        start = datetime.combine(report_date, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        run_id = uuid4()
        client = clickhouse()
        try:
            copy_rows(
                client,
                os.environ["CRM_DSN"],
                """SELECT p.id, c.keycloak_id, c.full_name, p.model
                   FROM prostheses p JOIN customers c ON c.id = p.customer_id""",
                (),
                "crm_prostheses",
                ["run_id", "prosthesis_id", "user_id", "customer_name", "model"],
                run_id,
            )
            copy_rows(
                client,
                os.environ["TELEMETRY_DSN"],
                """SELECT id, prosthesis_id, occurred_at, movement, response_ms, battery_level
                   FROM telemetry WHERE occurred_at >= %s AND occurred_at < %s""",
                (start, end),
                "telemetry",
                ["run_id", "event_id", "prosthesis_id", "occurred_at", "movement", "response_ms", "battery_level"],
                run_id,
            )
        finally:
            client.close()
        return {"run_id": str(run_id), "report_date": report_date.isoformat()}

    @task
    def build_mart(batch):
        client = clickhouse()
        # Каждая попытка получает свою версию витрины.
        report_run = uuid4()
        parameters = {
            "source_run": batch["run_id"],
            "report_run": str(report_run),
            "report_date": batch["report_date"],
        }
        try:
            unknown = client.query(
                """
                SELECT count()
                FROM telemetry t
                LEFT ANTI JOIN crm_prostheses c
                    ON t.run_id = c.run_id AND t.prosthesis_id = c.prosthesis_id
                WHERE t.run_id = {source_run:UUID}
                """,
                parameters=parameters,
            ).result_rows[0][0]
            if unknown:
                raise ValueError("В CRM нет владельца для части телеметрии")

            client.command(
                """
                INSERT INTO daily_reports
                SELECT {report_run:UUID}, {report_date:Date}, c.user_id,
                       t.prosthesis_id, c.customer_name, c.model,
                       count(), countIf(t.movement != 'idle'),
                       round(avg(t.response_ms), 2), round(avg(t.battery_level), 2)
                FROM telemetry t
                INNER JOIN crm_prostheses c
                    ON t.run_id = c.run_id AND t.prosthesis_id = c.prosthesis_id
                WHERE t.run_id = {source_run:UUID}
                GROUP BY c.user_id, t.prosthesis_id, c.customer_name, c.model
                """,
                parameters=parameters,
            )
            # Публикуем день только после записи всей витрины, даже если событий нет.
            client.insert(
                "completed_days",
                [(date.fromisoformat(batch["report_date"]), report_run, datetime.now(timezone.utc))],
                column_names=["report_date", "run_id", "completed_at"],
            )
        finally:
            client.close()

    build_mart(load_sources())


prepare_reports()
