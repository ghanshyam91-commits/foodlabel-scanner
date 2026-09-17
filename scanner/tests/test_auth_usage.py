from django.test import TestCase, override_settings
from django.core.cache import cache
from scanner.models import Account, MonthlyUsage

@override_settings(AUTH_REQUIRED=True,GOOGLE_AUTH_CONFIGURED=True,SESSION_ENGINE='django.contrib.sessions.backends.db')
class AuthAndUsageTests(TestCase):
    def signed_in(self,pin_hash=''):
        user=Account.objects.create(google_sub='google-123',email='person@example.com',pin_hash=pin_hash)
        session=self.client.session;session['account_id']=user.pk;session.save();return user
    def test_first_login_requires_pin_setup(self):
        self.signed_in();response=self.client.get('/');self.assertContains(response,'Create a 4-digit PIN')
    def test_pin_is_hashed_and_unlocks(self):
        user=self.signed_in();self.assertEqual(self.client.post('/auth/pin/setup/',{'pin':'1234'}).status_code,200)
        user.refresh_from_db();self.assertNotEqual(user.pin_hash,'1234');self.assertTrue(self.client.session['pin_unlocked'])
    @override_settings(USD_TO_INR_RATE=90)
    def test_usage_cost_uses_flash_lite_rates(self):
        user=self.signed_in('hash');session=self.client.session;session['pin_unlocked']=True;session.save()
        from datetime import date
        MonthlyUsage.objects.create(account=user,month=date.today().replace(day=1),model_name='gemini-2.5-flash-lite',scans=2,input_tokens=1_000_000,output_tokens=1_000_000)
        data=self.client.get('/api/usage/').json();self.assertEqual(data['scans'],2);self.assertEqual(data['estimated_usd'],0.5);self.assertEqual(data['estimated_inr'],45.0)
    @override_settings(SCANNER_ACCESS_CODE='old-private-beta-code')
    def test_google_pin_replaces_legacy_access_code(self):
        self.signed_in('hash');session=self.client.session;session['pin_unlocked']=True;session.save()
        self.assertFalse(self.client.get('/api/config/').json()['access_required'])

@override_settings(AUTH_REQUIRED=True,GOOGLE_AUTH_CONFIGURED=False,TEMPORARY_LOGIN_PIN='0608',
    SESSION_ENGINE='django.contrib.sessions.backends.db')
class TemporaryPinTests(TestCase):
    def setUp(self):cache.clear()
    def test_login_page_requests_pin_without_exposing_value(self):
        body=self.client.get('/').content.decode()
        self.assertIn('Temporary PIN',body);self.assertNotIn('0608',body)
    def test_wrong_pin_is_rejected(self):
        self.assertEqual(self.client.post('/auth/pin/temporary/',{'pin':'1234'}).status_code,403)
    def test_default_pin_unlocks_app(self):
        self.assertEqual(self.client.post('/auth/pin/temporary/',{'pin':'0608'}).status_code,200)
        self.assertContains(self.client.get('/'),'Explore Dutch Supermarkets')
    @override_settings(GOOGLE_AUTH_CONFIGURED=True)
    def test_temporary_pin_disabled_when_google_is_ready(self):
        self.assertEqual(self.client.post('/auth/pin/temporary/',{'pin':'0608'}).status_code,403)
