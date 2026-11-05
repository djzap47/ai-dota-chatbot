"""Offline regression checks: no API keys, network calls, or live database."""

import contextlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool

# Override any local .env credentials before importing application settings.
with patch.dict(os.environ, {
    "SUPABASE_DB_URL": "",
    "GOOGLE_API_KEY": "",
    "STRATZ_API_KEY": "",
    "CRON_SECRET": "",
}):
    from api import index
    from app import database
    from app.config import Settings
    from scripts.bulk_ingest_all_dota_knowledge import build_all_knowledge_chunks


ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def test_database_url_normalization_and_ssl(self):
        cases = [
            ("", ""),
            ("postgres://user:pass@localhost/db",
             "postgresql://user:pass@localhost/db?sslmode=require"),
            ("postgresql+psycopg://user:pass@localhost/db?connect_timeout=5",
             "postgresql+psycopg://user:pass@localhost/db?connect_timeout=5&sslmode=require"),
            ("postgresql://user:pass@localhost/db?sslmode=verify-full",
             "postgresql://user:pass@localhost/db?sslmode=verify-full"),
        ]
        with patch.dict(os.environ, {}, clear=True):
            for original, expected in cases:
                with self.subTest(uri=original):
                    config = Settings(_env_file=None, SUPABASE_DB_URL=original)
                    self.assertEqual(config.sqlalchemy_db_url, expected)

    def test_driver_options_match_the_selected_postgres_driver(self):
        # Intercept the DBAPI call itself: exercise the real engine without a socket.
        for scheme in ("postgresql", "postgresql+psycopg", "postgresql+psycopg2"):
            with self.subTest(scheme=scheme), contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(database, "_engine", None))
                stack.enter_context(patch.object(database, "_SessionLocal", None))
                stack.enter_context(patch.object(
                    database.settings, "SUPABASE_DB_URL",
                    f"{scheme}://test:test@localhost/test",
                ))
                engine = database.get_engine()
                stack.callback(engine.dispose)
                self.assertIsInstance(engine.pool, NullPool)
                self.assertIs(database.get_engine(), engine)
                with patch.object(
                    engine.dialect.loaded_dbapi, "connect",
                    side_effect=RuntimeError("connection intercepted"),
                ) as connect:
                    with self.assertRaisesRegex(RuntimeError, "connection intercepted"):
                        engine.raw_connection()
                options = connect.call_args.kwargs
                self.assertEqual(options["sslmode"], "require")
                if engine.dialect.driver == "psycopg":
                    self.assertIn("prepare_threshold", options)
                    self.assertIsNone(options["prepare_threshold"])
                else:
                    self.assertNotIn("prepare_threshold", options)

    def test_missing_database_url_fails_before_connecting(self):
        with patch.object(database, "_engine", None), patch.object(
            database.settings, "SUPABASE_DB_URL", ""
        ):
            with self.assertRaisesRegex(ValueError, "SUPABASE_DB_URL"):
                database.get_engine()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(index.app)
        self.addCleanup(self.client.close)
        secret_patch = patch.object(index.settings, "CRON_SECRET", "test-secret")
        secret_patch.start()
        self.addCleanup(secret_patch.stop)

    def test_home_serves_the_chat_interface(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('id="chatForm"', response.text)

    def test_openapi_exposes_the_documented_routes(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        for route in ("/", "/api/info", "/health", "/chat", "/heroes/top",
                      "/api/cron", "/scraper/run", "/scraper/sync-meta"):
            self.assertIn(route, paths)

    def test_blank_chat_does_not_call_the_model(self):
        with patch.object(index, "get_chat_response", new_callable=AsyncMock) as chat:
            response = self.client.post("/chat", json={"message": "  \n "})
        self.assertEqual(response.status_code, 400)
        chat.assert_not_awaited()

    def test_missing_chat_message_is_rejected(self):
        response = self.client.post("/chat", json={})
        self.assertEqual(response.status_code, 422)

    def test_chat_returns_the_service_reply(self):
        with patch.object(index, "get_chat_response", new_callable=AsyncMock,
                          return_value="Example reply") as chat:
            response = self.client.post("/chat", json={"message": "Pudge build?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"reply": "Example reply", "status": "success"})
        chat.assert_awaited_once_with("Pudge build?")

    def test_chat_service_exception_returns_500(self):
        with patch.object(index, "get_chat_response", new_callable=AsyncMock,
                          side_effect=RuntimeError("service unavailable")):
            response = self.client.post("/chat", json={"message": "Pudge build?"})
        self.assertEqual(response.status_code, 500)

    def test_health_checks_and_closes_the_database_session(self):
        session = MagicMock()
        with patch.object(index, "SessionLocal", return_value=session):
            response = self.client.get("/health")
        self.assertEqual(response.json()["status"], "healthy")
        session.execute.assert_called_once()
        session.close.assert_called_once()

    def test_health_reports_degraded_and_closes_on_query_failure(self):
        session = MagicMock()
        session.execute.side_effect = RuntimeError("database unavailable")
        with patch.object(index, "SessionLocal", return_value=session):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "degraded")
        session.close.assert_called_once()

    def test_scraper_routes_reject_missing_or_wrong_secrets(self):
        with patch.object(index, "run_scraper_task") as scraper, patch(
            "scripts.bulk_ingest_all_dota_knowledge.bulk_ingest_into_supabase"
        ) as ingest:
            for method, route in (("GET", "/api/cron"), ("POST", "/scraper/run"),
                                  ("POST", "/scraper/sync-meta")):
                for headers in ({}, {"Authorization": "Bearer incorrect"}):
                    with self.subTest(route=route, headers=headers):
                        response = self.client.request(method, route, headers=headers)
                        self.assertEqual(response.status_code, 401)
        scraper.assert_not_called()
        ingest.assert_not_called()

    def test_authorized_stats_sync_invalidates_the_chat_cache(self):
        for method, route in (("GET", "/api/cron"), ("POST", "/scraper/run")):
            with self.subTest(route=route), patch.object(
                index, "run_scraper_task", return_value=127
            ) as scraper, patch.object(index, "invalidate_stats_cache") as invalidate:
                response = self.client.request(
                    method, route, headers={"Authorization": "Bearer test-secret"}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["updated_count"], 127)
                scraper.assert_called_once()
                invalidate.assert_called_once()

    def test_authorized_knowledge_sync_returns_the_ingestion_count(self):
        with patch("scripts.bulk_ingest_all_dota_knowledge.bulk_ingest_into_supabase",
                   return_value=450) as ingest:
            response = self.client.post(
                "/scraper/sync-meta", headers={"Authorization": "Bearer test-secret"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated_count"], 450)
        ingest.assert_called_once()


class KnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datasets = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in (ROOT / "app" / "data").glob("*.json")
        }
        with contextlib.redirect_stdout(io.StringIO()):
            cls.chunks = build_all_knowledge_chunks()

    def test_builds_and_matchups_cover_the_bundled_heroes(self):
        hero_ids = set(self.datasets["heroes"])
        self.assertEqual(set(self.datasets["hero_builds"]), hero_ids)
        self.assertEqual(set(self.datasets["hero_matchups"]), hero_ids)

    def test_every_build_has_four_nonempty_game_phases(self):
        for hero_id, entry in self.datasets["hero_builds"].items():
            with self.subTest(hero=hero_id):
                self.assertTrue(entry["builds"])
                for build in entry["builds"]:
                    for phase in ("starting", "early", "mid", "late"):
                        self.assertIsInstance(build[phase], str)
                        self.assertTrue(build[phase].strip())

    def test_chunks_are_nonempty_and_have_unique_titles(self):
        titles = [title for _, title, _ in self.chunks]
        self.assertEqual(len(titles), len(set(titles)))
        for chunk in self.chunks:
            self.assertTrue(all(isinstance(value, str) and value.strip() for value in chunk))

    def test_ingestion_preserves_each_hero_build_variant(self):
        by_title = {title: content for _, title, content in self.chunks}
        for entry in self.datasets["hero_builds"].values():
            title = f"{entry['hero_name']} - High-MMR Item Build & Matchups"
            with self.subTest(hero=entry["hero_name"]):
                content = by_title[title]
                for build in entry["builds"]:
                    for phase in ("starting", "early", "mid", "late"):
                        self.assertIn(build[phase], content)


if __name__ == "__main__":
    unittest.main()
