CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.crm_prostheses
(
    run_id UUID,
    prosthesis_id String,
    user_id String,
    customer_name String,
    model String
)
ENGINE = MergeTree
ORDER BY (run_id, prosthesis_id);

CREATE TABLE IF NOT EXISTS bionicpro.telemetry
(
    run_id UUID,
    event_id UInt64,
    prosthesis_id String,
    occurred_at DateTime('UTC'),
    movement String,
    response_ms Float64,
    battery_level Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (run_id, prosthesis_id, occurred_at, event_id);

CREATE TABLE IF NOT EXISTS bionicpro.daily_reports
(
    run_id UUID,
    report_date Date,
    user_id String,
    prosthesis_id String,
    customer_name String,
    model String,
    events_count UInt64,
    movements_count UInt64,
    avg_response_ms Float64,
    avg_battery Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date, prosthesis_id, run_id);

CREATE TABLE IF NOT EXISTS bionicpro.completed_days
(
    report_date Date,
    run_id UUID,
    completed_at DateTime64(6, 'UTC')
)
ENGINE = MergeTree
ORDER BY (report_date, completed_at);

CREATE USER IF NOT EXISTS report_reader IDENTIFIED BY 'report_password';
GRANT SELECT ON bionicpro.daily_reports TO report_reader;
GRANT SELECT ON bionicpro.completed_days TO report_reader;
