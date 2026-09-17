from django.test import TestCase, override_settings
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
    def test_usage_cost_uses_flash_lite_rates(self):
        user=self.signed_in('hash');session=self.client.session;session['pin_unlocked']=True;session.save()
        from datetime import date
        MonthlyUsage.objects.create(account=user,month=date.today().replace(day=1),model_name='gemini-2.5-flash-lite',scans=2,input_tokens=1_000_000,output_tokens=1_000_000)
        data=self.client.get('/api/usage/').json();self.assertEqual(data['scans'],2);self.assertEqual(data['estimated_usd'],0.5)
    @override_settings(SCANNER_ACCESS_CODE='old-private-beta-code')
    def test_google_pin_replaces_legacy_access_code(self):
        self.signed_in('hash');session=self.client.session;session['pin_unlocked']=True;session.save()
        self.assertFalse(self.client.get('/api/config/').json()['access_required'])
