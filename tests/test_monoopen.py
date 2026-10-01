"""Офлайн-тесты MonoOpen: не ходят в сеть, проверяют разбор ответа."""
import unittest

from monoopen import read_json, to_text, get_cookies, Response, __version__
from monoopen import split_adres


class TestSplitAdres(unittest.TestCase):
    def test_https_prefix_and_path(self):
        self.assertEqual(split_adres("https://site.com/a/b?x=1"), ("site.com", "/a/b?x=1"))

    def test_no_path(self):
        self.assertEqual(split_adres("example.com"), ("example.com", "/"))


class TestToText(unittest.TestCase):
    def test_windows_1251_quoted(self):
        body = '<meta charset="windows-1251">Привет'.encode("windows-1251")
        self.assertIn("Привет", to_text(body))

    def test_utf8_no_quotes(self):
        body = b"<meta charset=utf-8>" + "Текст".encode("utf-8")
        self.assertIn("Текст", to_text(body))

    def test_spaces_around_eq(self):
        body = '<meta charset = "windows-1251">Мир'.encode("windows-1251")
        self.assertIn("Мир", to_text(body))

    def test_no_charset_defaults_utf8(self):
        self.assertEqual(to_text("просто".encode("utf-8")), "просто")


class TestCookies(unittest.TestCase):
    def test_multiple(self):
        z = (b"HTTP/1.1 200 OK\r\n"
             b"Set-Cookie: session=abc123; Path=/; HttpOnly\r\n"
             b"Set-Cookie: theme=dark; Path=/\r\n"
             b"set-cookie: lang=ru\r\n")
        self.assertEqual(get_cookies(z), {"session": "abc123", "theme": "dark", "lang": "ru"})

    def test_none(self):
        self.assertEqual(get_cookies(b"HTTP/1.1 200 OK\r\nServer: x\r\n"), {})


class TestResponse(unittest.TestCase):
    def test_text_and_json_and_cookies(self):
        headers = b"HTTP/1.1 200 OK\r\nSet-Cookie: a=1\r\n"
        r = Response(200, headers, b'{"name": "vlad", "n": 20}')
        self.assertEqual(r.code, 200)
        self.assertEqual(r.json(), {"name": "vlad", "n": 20})
        self.assertEqual(r.cookies(), {"a": "1"})

    def test_read_json(self):
        self.assertEqual(read_json(b'{"ok": true}'), {"ok": True})


class TestMeta(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.2.0")


if __name__ == "__main__":
    unittest.main()
