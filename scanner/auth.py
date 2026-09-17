import re
from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST
from .models import Account
from .throttle import QuotaUnavailable, client_id, hit

oauth=OAuth()
if settings.GOOGLE_AUTH_CONFIGURED:
    oauth.register('google',client_id=settings.GOOGLE_OAUTH_CLIENT_ID,client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',client_kwargs={'scope':'openid email profile'})

def account(request):
    account_id=request.session.get('account_id')
    if not account_id:return None
    try:return Account.objects.get(pk=account_id)
    except (Account.DoesNotExist,TypeError,ValueError):return None
def unlocked(request):return bool(account(request) and request.session.get('pin_unlocked'))
def login_page(request):
    user=account(request);state='signin' if not user else ('setup' if not user.pin_hash else 'unlock')
    return render(request,'scanner/login.html',{'state':state,'account':user,'oauth_configured':settings.GOOGLE_AUTH_CONFIGURED})
@require_GET
def google_start(request):
    if not settings.GOOGLE_AUTH_CONFIGURED:return redirect('/')
    return oauth.google.authorize_redirect(request,request.build_absolute_uri('/auth/google/callback/'))
@require_GET
def google_callback(request):
    if not settings.GOOGLE_AUTH_CONFIGURED:return redirect('/')
    try:
        token=oauth.google.authorize_access_token(request);info=token.get('userinfo') or oauth.google.parse_id_token(request,token)
        if not info.get('sub') or not info.get('email_verified'):raise ValueError('Unverified account')
        user,_=Account.objects.update_or_create(google_sub=str(info['sub']),defaults={'email':info.get('email',''),'name':info.get('name','')[:200]})
        request.session.flush();request.session['account_id']=user.pk;request.session['pin_unlocked']=False
    except Exception:
        return render(request,'scanner/login.html',{'state':'signin','oauth_configured':True,'auth_error':'Google sign-in could not be completed. Please try again.'},status=400)
    return redirect('/')
@require_POST
def pin_setup(request):
    user=account(request);pin=request.POST.get('pin','')
    if not user:return JsonResponse({'error':'Sign in with Google first.'},status=401)
    if user.pin_hash:return JsonResponse({'error':'A PIN already exists.'},status=409)
    if not re.fullmatch(r'\d{4}',pin):return JsonResponse({'error':'Enter exactly 4 digits.'},status=400)
    user.pin_hash=make_password(pin);user.save(update_fields=['pin_hash']);request.session['pin_unlocked']=True;request.session.cycle_key();return JsonResponse({'ok':True})
@require_POST
def pin_unlock(request):
    user=account(request)
    if not user:return JsonResponse({'error':'Sign in with Google first.'},status=401)
    try:
        if not hit(f'pin:{user.pk}:{client_id(request)}',5,600):return JsonResponse({'error':'Too many attempts. Try again in ten minutes.'},status=429)
    except QuotaUnavailable:return JsonResponse({'error':'PIN service is temporarily unavailable.'},status=503)
    if not check_password(request.POST.get('pin',''),user.pin_hash):return JsonResponse({'error':'That PIN did not match.'},status=403)
    request.session['pin_unlocked']=True;request.session.cycle_key();return JsonResponse({'ok':True})
@require_POST
def sign_out(request):request.session.flush();return JsonResponse({'ok':True})
