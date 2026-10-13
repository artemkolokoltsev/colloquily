"""Local ownership and account-free browser regression checks."""
import os
import tempfile
import unittest
from unittest.mock import patch

import config
from backend.main import app
from fastapi.testclient import TestClient
from services.database import create_user, get_local_user, init_db, list_users
from werkzeug.security import check_password_hash


class LocalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(config, 'DB_PATH', os.path.join(self.temp.name, 'test.db'))
        self.db_patch.start()
        init_db(seed_admin=False)
        self.client = TestClient(app)

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def test_new_workspace_has_no_default_password(self):
        owner = get_local_user()
        self.assertEqual(owner['username'], 'local')
        self.assertFalse(check_password_hash(owner['password_hash'], 'admin'))
        self.assertEqual(get_local_user()['id'], owner['id'])
        self.assertEqual(len(list_users()), 1)

    def test_legacy_owner_id_is_preserved(self):
        create_user('another', 'unused')
        create_user('admin', 'old-password', is_admin=True)
        owner = get_local_user()
        self.assertEqual(owner['username'], 'admin')
        self.assertEqual(get_local_user()['id'], owner['id'])
        self.assertEqual(len(list_users()), 2)

    def test_settings_are_available_without_login_or_admin_role(self):
        response = self.client.get('/api/settings')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), dict)
        self.assertFalse(get_local_user()['is_admin'])

    def test_old_account_routes_cannot_switch_or_create_accounts(self):
        owner = get_local_user()
        for path, fields in [('/login', {'username': 'other', 'password': 'admin'}),
                             ('/admin/users', {'username': 'other', 'password': 'admin'}),
                             ('/logout', {})]:
            self.assertEqual(self.client.post(path, data=fields).status_code, 404)
        self.assertEqual(get_local_user()['id'], owner['id'])
        self.assertEqual(len(list_users()), 1)
        self.assertEqual(self.client.get('/login').status_code, 404)
