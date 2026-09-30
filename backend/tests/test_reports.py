import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import app, get_database, issuer


class ReportsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.database = MagicMock()
        self.day = date(2026, 1, 10)
        self.run_id = uuid4()
        self.ready = SimpleNamespace(result_rows=[(self.day, self.run_id)])
        self.result = MagicMock()
        self.result.named_results.return_value = iter([])
        self.database.query.side_effect = [self.ready, self.result]
        app.dependency_overrides[get_database] = lambda: self.database
        self.client = TestClient(app)
        self.key_patch = patch('app.jwks.get_signing_key_from_jwt')
        self.key_patch.start().return_value = SimpleNamespace(key=self.private_key.public_key())

    def tearDown(self):
        self.client.close()
        self.key_patch.stop()
        app.dependency_overrides.clear()

    def token(self, **overrides):
        claims = {
            'sub': 'owner-1',
            'iss': issuer,
            'aud': 'reports-api',
            'exp': datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(claims, self.private_key, algorithm='RS256')

    def request(self, token=None, **query):
        params = {'date_from': self.day.isoformat(), 'date_to': self.day.isoformat()}
        params.update(query)
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        return self.client.get('/reports', params=params, headers=headers)

    def test_login_required(self):
        self.assertEqual(self.request().status_code, 401)
        self.database.query.assert_not_called()

    def test_invalid_tokens(self):
        tokens = [
            'broken',
            self.token(exp=datetime.now(timezone.utc) - timedelta(seconds=1)),
            self.token(aud='another-api'),
            self.token(iss='https://another-issuer'),
            self.token(sub=''),
            jwt.encode({'sub': 'owner-1'}, 'wrong-key', algorithm='HS256'),
        ]
        for token in tokens:
            with self.subTest(token=token[:15]):
                self.assertEqual(self.request(token).status_code, 401)
        self.database.query.assert_not_called()

    def test_owner_comes_from_token_even_for_admin(self):
        response = self.request(
            self.token(realm_access={'roles': ['administrator']}), user_id='owner-2'
        )
        self.assertEqual(response.status_code, 200)
        parameters = self.database.query.call_args.kwargs['parameters']
        self.assertEqual(parameters['user_id'], 'owner-1')
        self.assertEqual(parameters['runs'], [(self.day, str(self.run_id))])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_completed_day_without_telemetry_is_empty_report(self):
        response = self.request(self.token())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rows'], [])

    def test_unprocessed_day_is_not_an_empty_report(self):
        self.ready.result_rows = []
        response = self.request(self.token())
        self.assertEqual(response.status_code, 409)
        self.assertIn(self.day.isoformat(), response.json()['detail'])
        self.assertEqual(self.database.query.call_count, 1)

    def test_missing_day_inside_period_blocks_whole_report(self):
        self.ready.result_rows = [
            (self.day, self.run_id),
            (self.day + timedelta(days=2), uuid4()),
        ]
        response = self.request(self.token(), date_to='2026-01-12')
        self.assertEqual(response.status_code, 409)
        self.assertIn('2026-01-11', response.json()['detail'])
        self.assertEqual(self.database.query.call_count, 1)

    def test_invalid_periods(self):
        for query, code in [
            ({'date_to': '2026-01-09'}, 400),
            ({'date_from': 'not-a-date'}, 422),
        ]:
            with self.subTest(query=query):
                self.assertEqual(self.request(self.token(), **query).status_code, code)
        self.database.query.assert_not_called()


if __name__ == '__main__':
    unittest.main()
