import os
from datetime import date, timedelta

import clickhouse_connect
import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWTError

app = FastAPI(title="BionicPRO Reports")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["GET"],
    allow_headers=["Authorization"],
)

issuer = os.getenv("KEYCLOAK_ISSUER", "http://localhost:8080/realms/reports-realm")
audience = "reports-api"
jwks = PyJWKClient(
    os.getenv("KEYCLOAK_JWKS_URL", issuer + "/protocol/openid-connect/certs"),
    timeout=5,
)
bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if credentials is None:
        raise HTTPException(401, "Требуется вход", headers={"WWW-Authenticate": "Bearer"})
    try:
        key = jwks.get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials,
            key.key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        if not claims["sub"]:
            raise jwt.InvalidTokenError("Empty subject")
        return claims["sub"]
    except PyJWKClientConnectionError:
        raise HTTPException(503, "Сервис авторизации недоступен")
    except PyJWTError:
        raise HTTPException(401, "Недействительный токен", headers={"WWW-Authenticate": "Bearer"})


def get_database():
    try:
        client = clickhouse_connect.get_client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            username=os.getenv("CLICKHOUSE_USER", "report_reader"),
            password=os.getenv("CLICKHOUSE_PASSWORD", "report_password"),
            database="bionicpro",
            connect_timeout=5,
            send_receive_timeout=15,
        )
    except clickhouse_connect.driver.exceptions.ClickHouseError:
        raise HTTPException(503, "База отчётов недоступна")
    try:
        yield client
    finally:
        client.close()


@app.get("/reports")
def reports(
    response: Response,
    date_from: date = Query(...),
    date_to: date = Query(...),
    user_id: str = Depends(current_user),
    database=Depends(get_database),
):
    response.headers["Cache-Control"] = "no-store"
    if date_from > date_to:
        raise HTTPException(400, "Начало периода должно быть не позже конца")
    try:
        # Берём только полностью завершённые загрузки для каждого дня.
        ready = database.query(
            """
            SELECT report_date, argMax(run_id, completed_at) AS run_id
            FROM completed_days
            WHERE report_date BETWEEN {date_from:Date} AND {date_to:Date}
            GROUP BY report_date
            """,
            parameters={"date_from": date_from, "date_to": date_to},
        ).result_rows
        ready_dates = {row[0] for row in ready}
        requested_dates = [
            date_from + timedelta(days=offset)
            for offset in range((date_to - date_from).days + 1)
        ]
        missing = [day.isoformat() for day in requested_dates if day not in ready_dates]
        if missing:
            raise HTTPException(409, "Данные ещё не готовы за: " + ", ".join(missing))

        result = database.query(
            """
            SELECT report_date, prosthesis_id, customer_name, model,
                   events_count, movements_count, avg_response_ms, avg_battery
            FROM daily_reports
            WHERE user_id = {user_id:String}
              AND report_date BETWEEN {date_from:Date} AND {date_to:Date}
              AND (report_date, run_id) IN {runs:Array(Tuple(Date, UUID))}
            ORDER BY report_date, prosthesis_id
            """,
            parameters={
                "user_id": user_id,
                "date_from": date_from,
                "date_to": date_to,
                "runs": [(day, str(run_id)) for day, run_id in ready],
            },
        )
        rows = list(result.named_results())
    except clickhouse_connect.driver.exceptions.ClickHouseError:
        raise HTTPException(503, "Не удалось прочитать отчёт")

    return {"date_from": date_from, "date_to": date_to, "rows": rows}
