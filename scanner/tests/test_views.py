"""Django integration tests: run with python manage.py test."""
from unittest.mock import patch
from django.test import SimpleTestCase, Client, override_settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from scanner.demo import demo_label
from scanner.provider import ExtractionResult
from scanner.tests.test_images import image_bytes

@override_settings(GEMINI_API_KEY='test-key', SCANNER_ACCESS_CODE='', DEBUG=True)
class ViewTests(SimpleTestCase):
    def setUp(self):cache.clear()
    def test_home(self):
        response=self.client.get('/');self.assertEqual(response.status_code,200);self.assertContains(response,'Explore Dutch Supermarkets')
    def test_config_does_not_leak_keys(self):
        self.assertNotIn('test-key',self.client.get('/api/config/').content.decode())
    def test_demo_marked(self):
        response=self.client.get('/api/examples/oats/');self.assertTrue(response.json()['is_demo'])
    def test_no_cache_header(self):self.assertIn('no-store',self.client.get('/').headers['Cache-Control'])
    def test_no_photo(self):self.assertEqual(self.client.post('/api/scan/',{'consent':'yes'}).status_code,400)
    def test_no_consent(self):self.assertEqual(self.client.post('/api/scan/').status_code,400)
    def test_csrf_enforced(self):self.assertEqual(Client(enforce_csrf_checks=True).post('/api/scan/').status_code,403)
    @override_settings(GEMINI_API_KEY='')
    @patch('scanner.views.extract_label_local',return_value=ExtractionResult(demo_label('oats'),provider='Tesseract local OCR',model_name='tesseract-local'))
    def test_no_key_uses_local_ocr(self,mock_ocr):
        response=self.client.post('/api/scan/',{'consent':'yes','photo':SimpleUploadedFile('test.png',image_bytes(),content_type='image/png')})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['provider'],'Tesseract local OCR');mock_ocr.assert_called_once()
    @override_settings(SCANNER_ACCESS_CODE='a-long-private-code')
    def test_access_required(self):self.assertEqual(self.client.post('/api/scan/').status_code,403)
    @override_settings(SCANNER_ACCESS_CODE='a-long-private-code')
    def test_unlock(self):self.assertEqual(self.client.post('/api/unlock/',{'code':'a-long-private-code'}).status_code,200)
    @override_settings(SCANNER_ACCESS_CODE='a-long-private-code')
    def test_bad_code(self):self.assertEqual(self.client.post('/api/unlock/',{'code':'wrong'}).status_code,403)
    @patch('scanner.views.extract_label',return_value=demo_label('chocolate'))
    def test_upload_flow(self, mock_extract):
        response=self.client.post('/api/scan/',{'consent':'yes','preference':'vegan','photo':SimpleUploadedFile('test.png',image_bytes(),content_type='image/png')})
        self.assertEqual(response.status_code,200);self.assertFalse(response.json()['is_demo']);self.assertEqual(response.json()['assessment']['preference_match'],'no');mock_extract.assert_called_once()
    @override_settings(SCANS_PER_DAY=1)
    @patch('scanner.views.extract_label',return_value=demo_label('oats'))
    def test_daily_limit(self, _):
        def scan():return self.client.post('/api/scan/',{'consent':'yes','photo':SimpleUploadedFile('test.png',image_bytes(),content_type='image/png')})
        self.assertEqual(scan().status_code,200);self.assertEqual(scan().status_code,429)
    @patch('scanner.throttle.cache.add',side_effect=RuntimeError('cache failed'))
    def test_quota_fail_closed(self,_):self.assertEqual(self.client.post('/api/scan/').status_code,503)
