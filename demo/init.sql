-- Две тестовые базы вместо внешней CRM и существующей базы телеметрии.
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    keycloak_id TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL
);
CREATE TABLE prostheses (
    id TEXT PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    model TEXT NOT NULL
);
INSERT INTO customers VALUES
    (1, '11111111-1111-4111-8111-111111111111', 'Иван Петров'),
    (2, '22222222-2222-4222-8222-222222222222', 'Анна Смирнова'),
    (3, '33333333-3333-4333-8333-333333333333', 'Олег Иванов');
INSERT INTO prostheses VALUES
    ('P-101', 1, 'Bionic Hand'),
    ('P-102', 1, 'Bionic Hand'),
    ('P-201', 2, 'Bionic Hand'),
    ('P-301', 3, 'Bionic Hand');

CREATE DATABASE telemetry;
\connect telemetry
CREATE TABLE telemetry (
    id BIGSERIAL PRIMARY KEY,
    prosthesis_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    movement TEXT NOT NULL,
    response_ms DOUBLE PRECISION NOT NULL,
    battery_level DOUBLE PRECISION NOT NULL
);
CREATE INDEX ON telemetry (occurred_at);

-- По 10 событий в день за последнюю неделю, а также за текущий день.
-- У P-301 телеметрии нет: его владелец получит пустой готовый отчёт.
INSERT INTO telemetry (prosthesis_id, occurred_at, movement, response_ms, battery_level)
SELECT p.id,
       date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
           - d * interval '1 day' + n * interval '1 hour',
       CASE WHEN n % 4 = 0 THEN 'idle' ELSE 'grip' END,
       p.response_ms + n,
       100 - n * 3
FROM (VALUES ('P-101', 80), ('P-102', 90), ('P-201', 100)) p(id, response_ms)
CROSS JOIN generate_series(0, 7) d
CROSS JOIN generate_series(1, 10) n;
