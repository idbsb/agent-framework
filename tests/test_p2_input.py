"""SYNTHETIC TEST DATA / NOT REAL RECRUITMENT DATA; no real documents."""
import asyncio
import unittest
from src.core.resume_files import capabilities, parse_file, FileInputError, MAX_FILE_BYTES
from test_p1_api import request


class InputTest(unittest.TestCase):
    def test_binary_file_api_rejects_without_parsing_or_persisting(self):
        from src.api.app import app
        async def binary_request(content, mime):
            output = []
            async def receive():
                return dict(type='http.request', body=content, more_body=False)
            async def send(message):
                output.append(message)
            path = '/api/resume/file/preview'
            await app(dict(type='http', asgi={'version': '3.0'}, http_version='1.1', method='POST', scheme='http',
                           path=path, raw_path=path.encode(), query_string=b'filename=synthetic.pdf', root_path='',
                           headers=[(b'content-type', mime)], client=('127.0.0.1', 1000), server=('127.0.0.1', 8000)), receive, send)
            return next(r['status'] for r in output if r['type'] == 'http.response.start')
        self.assertEqual(asyncio.run(binary_request(b'%PDF-SYNTHETIC TEST DATA', b'application/pdf')), 501)
        self.assertEqual(asyncio.run(binary_request(b'', b'application/pdf')), 422)
        self.assertEqual(asyncio.run(binary_request(b'SYNTHETIC TEST DATA', b'text/html')), 415)
        self.assertEqual(asyncio.run(binary_request(b'x'*(MAX_FILE_BYTES+1), b'application/pdf')), 413)

    def test_capability_honest(self):
        value = capabilities()
        self.assertFalse(value['pdf']['supported'])
        self.assertFalse(value['docx']['supported'])
        self.assertTrue(value['text']['supported'])
        self.assertTrue(value['requires_user_confirmation'])

    def test_file_types_rejected(self):
        for name, mime in [('synthetic.exe', 'application/octet-stream'), ('synthetic.pdf', 'text/html'), ('synthetic.docm', 'application/zip')]:
            with self.subTest(name=name), self.assertRaises(FileInputError) as caught:
                parse_file(name, mime, b'SYNTHETIC TEST DATA')
            self.assertEqual(caught.exception.status, 415)

    def test_empty_and_oversize_rejected(self):
        for content, status in [(b'', 422), (b'x'*(MAX_FILE_BYTES+1), 413)]:
            with self.assertRaises(FileInputError) as caught:
                parse_file('synthetic.pdf', 'application/pdf', content)
            self.assertEqual(caught.exception.status, status)

    def test_missing_dependency_not_fake_parse_success(self):
        with self.assertRaises(FileInputError) as caught:
            parse_file('synthetic.pdf', 'application/pdf', b'%PDF-SYNTHETIC TEST DATA')
        self.assertEqual(caught.exception.code, 'DEPENDENCY_REQUIRED')
        self.assertEqual(caught.exception.status, 501)

    def test_capability_api(self):
        status, value = asyncio.run(request('GET', '/api/resume/file/capabilities'))
        self.assertEqual(status, 200)
        self.assertFalse(value['pdf']['supported'])

    def test_quality_preview_is_readonly_and_validates_ids(self):
        from fixtures.p2_synthetic.synthetic_fixture import jd
        status, value = asyncio.run(request('POST', '/api/quality/preview', {'rows': [jd(), jd(2)]}))
        self.assertEqual(status, 200)
        self.assertEqual(value['independent_evidence_count'], 1)
        self.assertEqual(asyncio.run(request('POST', '/api/quality/preview', {'rows': [jd(), jd()]}))[0], 422)
