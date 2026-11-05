"""Regression tests for the audit findings; no live credentials or network."""
import asyncio
import contextlib
import io
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Imports the app with empty credentials, before any service is initialized.
from test_project import index, database, ROOT
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.middleware import ChatBodyLimitMiddleware
from app.services import chatbot, embeddings, knowledge_store, rag, rate_limit
from app.services.errors import ServiceError
from scripts import bulk_ingest_all_dota_knowledge as bulk
from scripts.fetch_hero_builds_and_matchups import normalize_build


class SecurityApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(index.app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def test_maintenance_is_disabled_without_secret(self):
        with patch.object(index, 'run_scraper_task') as sync, patch.object(bulk, 'bulk_ingest_into_supabase') as ingest:
            for secret in ('', '   '):
                with patch.object(index.settings, 'CRON_SECRET', secret):
                    for method, route in [('GET', '/api/cron'), ('POST', '/scraper/run'), ('POST', '/scraper/sync-meta')]:
                        self.assertEqual(self.client.request(method, route).status_code, 503)
            sync.assert_not_called()
            ingest.assert_not_called()

    def test_query_token_and_raw_header_are_rejected(self):
        with patch.object(index.settings, 'CRON_SECRET', 'test-secret'), patch.object(index, 'run_scraper_task') as sync:
            for headers in ({}, {'Authorization': 'test-secret'}):
                self.assertEqual(self.client.post('/scraper/run?secret=test-secret', headers=headers).status_code, 401)
            sync.assert_not_called()
            with self.assertRaises(HTTPException) as error:
                index.verify_auth('Bearer чужой')
            self.assertEqual(error.exception.status_code, 401)

    def test_chat_limits_reject_before_budget_or_generation(self):
        with patch.object(index, 'consume_chat_budget') as budget, patch.object(index, 'get_chat_response', new_callable=AsyncMock) as chat:
            self.assertEqual(self.client.post('/chat', json={'message': 'a' * 2001}).status_code, 422)
            self.assertEqual(self.client.post('/chat', content=b'x' * 16385).status_code, 413)
            budget.assert_not_called()
            chat.assert_not_awaited()

    def test_exhausted_budget_prevents_model_calls(self):
        with patch.object(index, 'consume_chat_budget', side_effect=ServiceError('Try later.', 429)), patch.object(index, 'get_chat_response', new_callable=AsyncMock) as chat:
            response = self.client.post('/chat', json={'message': 'Pudge?'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['retry-after'], '60')
        chat.assert_not_awaited()

    def test_database_and_sync_errors_do_not_leak(self):
        marker = 'postgresql://private:secret@internal/db'
        with patch.object(index, 'SessionLocal', side_effect=RuntimeError(marker)):
            response = self.client.get('/health')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(marker, response.text)
        with patch.object(index.settings, 'CRON_SECRET', 'test'), patch.object(index, 'run_scraper_task', side_effect=RuntimeError(marker)):
            response = self.client.post('/scraper/run', headers={'Authorization': 'Bearer test'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(marker, response.text)

    def test_provider_error_is_not_a_success_reply(self):
        with patch.object(index, 'consume_chat_budget'), patch.object(chatbot, 'build_system_prompt', return_value='context'), patch.object(rag, 'search_dota_knowledge', return_value=[]), patch.object(chatbot, 'get_llm') as get_llm:
            for failure, status in [('429 RESOURCE_EXHAUSTED private-token', 429), ('private-token', 503)]:
                get_llm.return_value.invoke.side_effect = RuntimeError(failure)
                response = self.client.post('/chat', json={'message': 'Pudge?'})
                self.assertEqual(response.status_code, status)
                self.assertNotIn('reply', response.json())
                self.assertNotIn('private-token', response.text)


class ResourceLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_chunked_body_is_capped_before_application(self):
        app = AsyncMock()
        middleware = ChatBodyLimitMiddleware(app, max_bytes=10)
        receive = AsyncMock(side_effect=[
            {'type': 'http.request', 'body': b'123456', 'more_body': True},
            {'type': 'http.request', 'body': b'78901', 'more_body': False},
        ])
        send = AsyncMock()
        await middleware({'type': 'http', 'path': '/chat'}, receive, send)
        app.assert_not_awaited()
        self.assertEqual(send.call_args_list[0].args[0]['status'], 413)

    async def test_cancelled_request_keeps_slot_until_worker_finishes(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        def worker(_):
            started.set()
            try:
                release.wait(5)
                return 'ok'
            finally:
                finished.set()
        slots = threading.BoundedSemaphore(1)
        with patch.object(chatbot, '_chat_slots', slots), patch.object(chatbot, '_run_chatbot_sync', side_effect=worker):
            task = asyncio.create_task(chatbot.get_chat_response('first'))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                with self.assertRaises(ServiceError) as error:
                    await chatbot.get_chat_response('second')
                self.assertEqual(error.exception.status_code, 429)
            finally:
                release.set()
                await asyncio.to_thread(finished.wait, 2)
                self.assertTrue(await asyncio.to_thread(slots.acquire, True, 2))
                slots.release()


class ProviderConfigurationTests(unittest.TestCase):
    def test_sdk_receives_one_attempt_and_bounded_timeout(self):
        from google.genai import types
        with patch.object(chatbot.settings, 'GOOGLE_API_KEY', 'test-key'):
            model = chatbot.get_llm()
        response = types.GenerateContentResponse(candidates=[types.Candidate(
            content=types.Content(parts=[types.Part(text='Answer')])
        )])
        try:
            with patch.object(model.client.models, 'generate_content', return_value=response) as generate:
                self.assertEqual(model.invoke('Question').content, 'Answer')
            options = generate.call_args.kwargs['config'].http_options
            self.assertEqual(options.retry_options.attempts, 1)
            self.assertEqual(options.timeout, chatbot.settings.UPSTREAM_TIMEOUT_SECONDS * 1000)
        finally:
            model.client.close()


class DatabaseTests(unittest.TestCase):
    def test_initialization_is_atomic_across_threads(self):
        entered, release = threading.Event(), threading.Event()
        engine = MagicMock()
        session_factory = MagicMock(return_value='session')
        def make_factory(**kwargs):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test timed out')
            return session_factory
        with patch.object(database, '_engine', None), patch.object(database, '_SessionLocal', None), patch.object(database.settings, 'SUPABASE_DB_URL', 'postgresql://test:test@localhost/test'), patch.object(database, 'create_engine', return_value=engine) as create, patch.object(database.event, 'listens_for', return_value=lambda f: f), patch.object(database, 'sessionmaker', side_effect=make_factory):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(database.SessionLocal)
                try:
                    self.assertTrue(entered.wait(2))
                    self.assertIsNone(database._engine)
                    second = executor.submit(database.SessionLocal)
                finally:
                    release.set()
                self.assertEqual(first.result(3), 'session')
                self.assertEqual(second.result(3), 'session')
            create.assert_called_once()

    def test_budget_fails_closed_when_storage_is_unavailable(self):
        with patch.object(rate_limit, 'SessionLocal', side_effect=RuntimeError('secret')):
            with self.assertRaises(ServiceError) as error:
                rate_limit.consume_chat_budget()
        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn('secret', str(error.exception))


def rows_result(rows):
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    return result


class RetrievalTests(unittest.TestCase):
    def test_keyword_results_respect_limit_without_calling_embeddings(self):
        db = MagicMock()
        db.execute.return_value = rows_result([
            {'hero_name': str(i), 'section_title': str(i), 'content': 'text', 'similarity': 1.0}
            for i in range(5)
        ])
        with patch.object(rag, 'SessionLocal') as session, patch.object(rag, 'generate_embedding') as embed:
            session.return_value.__enter__.return_value = db
            self.assertEqual(len(rag.search_dota_knowledge('pudge', limit=2)), 2)
        embed.assert_not_called()
        self.assertEqual(db.execute.call_count, 1)

    def test_repeated_keywords_have_bounded_queries_on_embedding_failure(self):
        db = MagicMock()
        db.execute.return_value = rows_result([])
        with patch.object(rag, 'SessionLocal') as session, patch.object(rag, 'generate_embedding', side_effect=RuntimeError('quota')):
            session.return_value.__enter__.return_value = db
            self.assertEqual(rag.search_dota_knowledge('pudge ' * 200), [])
        self.assertEqual(db.execute.call_count, 2)
        self.assertEqual(db.execute.call_args_list[0].args[1]['patterns'], ['%pudge%'])
        self.assertEqual(len(rag.extract_keywords('alpha beta gamma delta epsilon zeta eta theta iota kappa')), 8)

    def test_limit_and_threshold_are_enforced(self):
        db = MagicMock()
        db.execute.side_effect = [rows_result([]), rows_result([
            {'hero_name': 'a', 'section_title': 'a', 'content': 'a', 'similarity': 0.2},
            {'hero_name': 'b', 'section_title': 'b', 'content': 'b', 'similarity': 0.9},
            {'hero_name': 'c', 'section_title': 'c', 'content': 'c', 'similarity': 0.95},
        ])]
        with patch.object(rag, 'SessionLocal') as session, patch.object(rag, 'generate_embedding', return_value=[0.0] * 768):
            session.return_value.__enter__.return_value = db
            result = rag.search_dota_knowledge('pudge', limit=1, threshold=0.8)
        self.assertEqual([r['hero_name'] for r in result], ['b'])
        parameters = db.execute.call_args.args[1]
        self.assertEqual(parameters['model'], rag.settings.EMBEDDING_MODEL)
        self.assertEqual(parameters['threshold'], 0.8)

    def test_failed_vector_transaction_is_rolled_back_before_fallback(self):
        db = MagicMock()
        failed = False
        def execute(sql, params):
            nonlocal failed
            if ':vector' in str(sql):
                failed = True
                raise RuntimeError('vector query failed')
            self.assertFalse(failed, 'fallback used an aborted transaction')
            return rows_result([])
        def rollback():
            nonlocal failed
            failed = False
        db.execute.side_effect, db.rollback.side_effect = execute, rollback
        with patch.object(rag, 'SessionLocal') as session, patch.object(rag, 'generate_embedding', return_value=[0.0] * 768):
            session.return_value.__enter__.return_value = db
            rag.search_dota_knowledge('pudge')
        self.assertEqual(db.execute.call_count, 3)
        self.assertFalse(failed)

    def test_embeddings_never_switch_models_on_failure(self):
        embeddings._embed.cache_clear()
        self.addCleanup(embeddings._embed.cache_clear)
        client = MagicMock()
        client.models.embed_content.side_effect = RuntimeError('quota')
        with patch.object(embeddings, 'get_genai_client', return_value=client), patch.object(embeddings.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                embeddings.embed_batch_with_retry(['Pudge'], max_retries=2)
        self.assertEqual([c.kwargs['model'] for c in client.models.embed_content.call_args_list], [embeddings.settings.EMBEDDING_MODEL] * 2)
        for invalid in ([1.0], [float('nan')] * 768, [float('inf')] * 768):
            with self.assertRaises(ValueError):
                embeddings.validate_embedding(invalid)

    def test_embedding_cache_separates_models_and_preserves_case(self):
        embeddings._embed.cache_clear()
        self.addCleanup(embeddings._embed.cache_clear)
        client = MagicMock()
        client.models.embed_content.return_value.embeddings = [MagicMock(values=[0.1] * 768)]
        with patch.object(embeddings, 'get_genai_client', return_value=client):
            with patch.object(embeddings.settings, 'EMBEDDING_MODEL', 'first-model'):
                embeddings.generate_embedding('Pudge')
                embeddings.generate_embedding('Pudge')
                embeddings.generate_embedding('pudge')
            with patch.object(embeddings.settings, 'EMBEDDING_MODEL', 'second-model'):
                embeddings.generate_embedding('Pudge')
        calls = client.models.embed_content.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual([(c.kwargs['model'], c.kwargs['contents']) for c in calls], [
            ('first-model', 'Pudge'), ('first-model', 'pudge'), ('second-model', 'Pudge')
        ])


class IngestionTests(unittest.TestCase):
    def test_missing_or_empty_dataset_cannot_touch_database(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(bulk, 'DATA_DIR', Path(directory)), patch.object(knowledge_store, 'SessionLocal') as session:
            with self.assertRaises(FileNotFoundError):
                bulk.bulk_ingest_into_supabase()
            (Path(directory) / 'heroes.json').write_text('{}')
            with self.assertRaises(ValueError):
                bulk.bulk_ingest_into_supabase()
            session.assert_not_called()

    def test_item_document_preserves_ability_and_stat_labels(self):
        item = json.loads((ROOT / 'app/data/items.json').read_text(encoding='utf-8'))['black_king_bar']
        effects, stats = bulk.describe_item(item)
        self.assertIn('Avatar', effects)
        self.assertIn('Strength', stats)
        self.assertIn(item['abilities'][0]['description'], effects)

    def test_curated_variants_survive_fetch_normalization(self):
        builds = json.loads((ROOT / 'app/data/hero_builds.json').read_text(encoding='utf-8'))
        for entry in builds.values():
            self.assertEqual(normalize_build(entry, entry['hero_name']), entry)
        flat = dict(starting='a', early='b', mid='c', late='d')
        self.assertEqual(normalize_build(flat, 'Hero')['builds'][0]['mid'], 'c')

    def test_invalid_replacements_never_open_a_session(self):
        with patch.object(knowledge_store, 'SessionLocal') as session:
            for chunks in ([], [('a', 'b', '')], [('a', 'b', 'c')] * 2):
                with self.assertRaises(ValueError):
                    knowledge_store.replace_documents(chunks, replace_all=True)
            session.assert_not_called()

    def test_insert_failure_exits_transaction_with_exception(self):
        db, transaction = MagicMock(), MagicMock()
        db.begin.return_value = transaction
        db.execute.side_effect = [MagicMock(scalar=lambda: True), MagicMock(), RuntimeError('insert failed')]
        with patch.object(knowledge_store, 'SessionLocal') as session:
            session.return_value.__enter__.return_value = db
            with self.assertRaises(RuntimeError):
                knowledge_store.replace_documents([('a', 'b', 'c')], replace_all=True)
        self.assertEqual(transaction.__exit__.call_args.args[0], RuntimeError)
        db.commit.assert_not_called()

    def test_text_remains_committed_when_embedding_fails(self):
        chunks = [('Hero', 'Title', 'Knowledge')]
        with patch.object(bulk, 'build_all_knowledge_chunks', return_value=chunks), patch.object(bulk, 'replace_documents', return_value=[123]) as replace, patch.object(bulk, 'embed_batch_with_retry', side_effect=RuntimeError('quota')), patch.object(bulk, 'SessionLocal') as session, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bulk.bulk_ingest_into_supabase(), 1)
        replace.assert_called_once_with(chunks, replace_all=True)
        session.assert_not_called()
