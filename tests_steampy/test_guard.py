import json
import os
import tempfile
from base64 import b64encode
from unittest import TestCase

from src.steampy import guard
from src.steampy.confirmation import Tag


class TestGuard(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared_secret = b64encode(b'1234567890abcdefghij')
        cls.identity_secret = b64encode(b'abcdefghijklmnoprstu')

    def test_one_time_code(self):
        timestamp = 1469184207
        code = guard.generate_one_time_code(self.shared_secret, timestamp)
        assert code == 'P2QJN'

    def test_confirmation_key(self):
        timestamp = 1470838334
        confirmation_key = guard.generate_confirmation_key(self.identity_secret, Tag.CONF.value, timestamp)
        assert confirmation_key == b'pWqjnkcwqni+t/n+5xXaEa0SGeA='

    def test_generate_device_id(self):
        steam_id = '12341234123412345'
        device_id = guard.generate_device_id(steam_id)
        assert device_id == 'android:677cf5aa-3300-7807-d1e2-c408142742e2'

    def test_load_steam_guard(self):
        expected_keys = ('steamid', 'shared_secret', 'identity_secret')

        guard_json_str = '{"steamid": 12345678, "shared_secret": "SHARED_SECRET", "identity_secret": "IDENTITY_SECRET"}'
        guard_data = guard.load_steam_guard(guard_json_str)

        for key in expected_keys:
            assert key in guard_data
            assert isinstance(guard_data[key], str)

    def test_load_steam_guard_from_file(self):
        payload = {
            "steamid": 12345678,
            "shared_secret": "SHARED_SECRET",
            "identity_secret": "IDENTITY_SECRET",
        }

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".maFile", delete=False) as file:
            json.dump(payload, file)
            file_path = file.name

        try:
            guard_data = guard.load_steam_guard(file_path)
            assert guard_data["steamid"] == "12345678"
            assert guard_data["shared_secret"] == "SHARED_SECRET"
            assert guard_data["identity_secret"] == "IDENTITY_SECRET"
        finally:
            os.remove(file_path)

    def test_load_steam_guard_missing_path_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            guard.load_steam_guard("accounts_info/not_exists_guard.maFile")
