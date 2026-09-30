# Задание 2. Сервис отчётов

[Диаграмма C4](BionicPRO.drawio).

## Решение

В учебном стенде две базы PostgreSQL заменяют CRM и базу телеметрии. DAG `prepare_reports` каждый день в 00:00 UTC переносит данные за прошедшие сутки в ClickHouse и готовит витрину `daily_reports`. Одна строка содержит данные одного пользователя, протеза и дня.

После полной обработки DAG отмечает день в `completed_days`. API возвращает отчёт только за готовые дни: если в выбранном периоде есть необработанные даты, ответ — `409`. За готовый день без телеметрии вернётся пустой отчёт.

`GET /reports` проверяет JWT. Пользователь определяется по `sub` из токена, поэтому выбрать чужой отчёт через параметр запроса нельзя. Интерфейс позволяет выбрать период, посмотреть отчёт и скачать его в JSON.

## Запуск

Из корня репозитория:

```bash
docker compose up --build -d
```

- Интерфейс: http://localhost:3000
- API: http://localhost:8000/docs
- Keycloak: http://localhost:8080 (`admin` / `admin`)
- Airflow: http://localhost:8081 (`admin`)

Пароль Airflow создаётся при первом запуске:

```bash
docker compose exec airflow cat /opt/airflow/state/standalone_admin_password.txt
```

Тестовые пользователи: `prothetic1`, `prothetic2`, `prothetic3`; пароль у всех `prothetic123`. У первых двух есть телеметрия, у третьего — пустой отчёт. Тестовые события создаются при первом запуске базы за последние семь дней. Дождитесь запуска DAG, войдите в приложение, выберите период и нажмите «Получить отчёт».

Для запуска обработки прошлого дня укажите его дату:

```bash
docker compose exec airflow airflow dags trigger prepare_reports --conf '{"report_date":"2026-09-27"}'
```

Если realm уже был создан, Keycloak не применит новый экспорт автоматически. Добавьте Audience mapper `reports-api` для клиента `reports-frontend` и сверьте `customers.keycloak_id` с ID пользователей в Keycloak. При первом запуске эти настройки уже заданы в `keycloak/realm-export.json` и `demo/init.sql`.

## Проверка

API-тесты проверяют авторизацию, владельца отчёта и готовность периода:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

Сборка интерфейса:

```bash
cd frontend
npm ci
npm run build
```
