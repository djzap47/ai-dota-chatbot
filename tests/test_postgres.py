"""Real PostgreSQL checks. Only an explicitly named disposable dota_test DB is accepted."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from test_project import index
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.services import knowledge_store, rate_limit, rag
from app.services.errors import ServiceError

TEST_URL = os.environ.get('TEST_DATABASE_URL', '')


@unittest.skipUnless(TEST_URL, 'Set TEST_DATABASE_URL to a disposable dota_test PostgreSQL database')
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if make_url(TEST_URL).database != 'dota_test':
            raise ValueError('Integration tests require a disposable database named dota_test')
        cls.engine = create_engine(TEST_URL, poolclass=NullPool)
        cls.session = sessionmaker(bind=cls.engine)
        root = Path(__file__).resolve().parents[1]
        with cls.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            # Send whole SQL scripts without parameters (DO blocks contain %I).
            with connection.connection.driver_connection.cursor() as cursor:
                cursor.execute((root / 'schema.sql').read_text(encoding='utf-8'))
                # Applying the migration twice must be safe.
                cursor.execute((root / 'migrations/001_security.sql').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as connection:
            connection.execute(text('DELETE FROM hero_documents'))
            connection.execute(text('DELETE FROM chat_request_limits'))

    def test_concurrent_budget_and_window_reset(self):
        def request(_):
            try:
                rate_limit.consume_chat_budget()
                return 200
            except ServiceError as error:
                return error.status_code
        with patch.object(rate_limit, 'SessionLocal', self.session), patch.object(rate_limit.settings, 'CHAT_REQUESTS_PER_MINUTE', 3):
            with ThreadPoolExecutor(max_workers=8) as executor:
                statuses = list(executor.map(request, range(12)))
            self.assertEqual(statuses.count(200), 3)
            self.assertEqual(statuses.count(429), 9)
            with self.engine.begin() as connection:
                connection.execute(text("UPDATE chat_request_limits SET window_start = now() - INTERVAL '2 minutes'"))
            rate_limit.consume_chat_budget()
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT request_count FROM chat_request_limits')).scalar_one(), 1)

    def test_failed_insert_preserves_previous_snapshot(self):
        with patch.object(knowledge_store, 'SessionLocal', self.session):
            knowledge_store.replace_documents([('old', 'old title', 'old content')], replace_all=True)
            with self.engine.begin() as connection:
                connection.execute(text("ALTER TABLE hero_documents ADD CONSTRAINT test_reject_document CHECK (content <> 'reject')"))
            try:
                with self.assertRaises(Exception):
                    knowledge_store.replace_documents([('new', 'new title', 'valid'), ('bad', 'bad title', 'reject')], replace_all=True)
                with self.engine.connect() as connection:
                    self.assertEqual(connection.execute(text('SELECT content FROM hero_documents')).scalars().all(), ['old content'])
            finally:
                with self.engine.begin() as connection:
                    connection.execute(text('ALTER TABLE hero_documents DROP CONSTRAINT test_reject_document'))

    def test_retrieval_only_compares_matching_vector_spaces(self):
        vector = [1.0] + [0.0] * 767
        with patch.object(knowledge_store, 'SessionLocal', self.session):
            knowledge_store.replace_documents([('match', 'match', 'correct model')], embeddings=[vector])
            with patch.object(knowledge_store.settings, 'EMBEDDING_MODEL', 'incompatible'):
                knowledge_store.replace_documents([('other', 'other', 'wrong model')], embeddings=[vector])
        with patch.object(rag, 'SessionLocal', self.session), patch.object(rag, 'generate_embedding', return_value=vector):
            results = rag.search_dota_knowledge('unrelated', threshold=0.99)
        self.assertEqual([r['content'] for r in results], ['correct model'])

    def test_backend_tables_have_row_level_security(self):
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT relname, relrowsecurity FROM pg_class
                WHERE oid IN ('heroes'::regclass, 'hero_stats'::regclass,
                              'hero_documents'::regclass, 'chat_request_limits'::regclass)
            """)).all()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(enabled for _, enabled in rows))
