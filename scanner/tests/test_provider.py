import json
import unittest
from unittest.mock import patch
import httpx
from scanner.provider import extract_label, ProviderError
from scanner.demo import demo_label
OriginalClient=httpx.Client

class ProviderTests(unittest.TestCase):
    def run_response(self, status=200, body=None):
        data=body if body is not None else {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':demo_label('oats').model_dump_json()}]}}]}
        seen=[]
        def handler(request):
            seen.append(request);return httpx.Response(status,json=data)
        with patch('scanner.provider.httpx.Client',side_effect=lambda **kwargs:OriginalClient(transport=httpx.MockTransport(handler))):
            result=extract_label(b'jpeg','test-key','gemini-3.1-flash-lite')
        return result,seen
    def test_parses_valid_response(self):
        result,_=self.run_response();self.assertEqual(result.product_name,'Oat drink — sample')
    def test_key_header_not_url(self):
        _,seen=self.run_response();self.assertEqual(seen[0].headers['x-goog-api-key'],'test-key');self.assertNotIn('test-key',str(seen[0].url))
    def test_bounded_structured_no_tools(self):
        _,seen=self.run_response();body=json.loads(seen[0].content);self.assertIn('responseJsonSchema',body['generationConfig']);self.assertNotIn('tools',body)
    def test_no_key(self):
        with self.assertRaises(ProviderError):extract_label(b'jpeg','','gemini-3.1-flash-lite')
    def test_invalid_model(self):
        with self.assertRaises(ProviderError):extract_label(b'jpeg','key','../../unsafe')
    def test_upstream_429(self):
        with self.assertRaises(ProviderError):self.run_response(429)
    def test_upstream_403(self):
        with self.assertRaises(ProviderError):self.run_response(403)
    def test_upstream_500(self):
        with self.assertRaises(ProviderError):self.run_response(500)
    def test_empty_candidates(self):
        with self.assertRaises(ProviderError):self.run_response(body={'candidates':[]})
    def test_truncated_result(self):
        with self.assertRaises(ProviderError):self.run_response(body={'candidates':[{'finishReason':'MAX_TOKENS'}]})
    def test_invalid_json(self):
        with self.assertRaises(ProviderError):self.run_response(body={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'not JSON'}]}}]})
    def test_invalid_schema(self):
        with self.assertRaises(ProviderError):self.run_response(body={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"verdict":"vegan"}'}]}}]})
    def test_oversized_response(self):
        with self.assertRaises(ProviderError):self.run_response(body={'padding':'a'*260000})
    def test_timeout(self):
        def handler(request):raise httpx.ReadTimeout('timeout')
        with patch('scanner.provider.httpx.Client',side_effect=lambda **kwargs:OriginalClient(transport=httpx.MockTransport(handler))):
            with self.assertRaises(ProviderError):extract_label(b'jpeg','key','gemini-3.1-flash-lite')
