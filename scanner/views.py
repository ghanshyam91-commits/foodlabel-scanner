import hmac
from datetime import date
from django.conf import settings
from django.db.models import F, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from .demo import EXAMPLES, demo_label
from .images import MAX_BYTES, ImageInputError, prepare_image
from .provider import ProviderError, extract_label
from .local_ocr import extract_label_local
from .shop_search import (
    RETAILERS, ShopSearchError, build_shop_search, fallback_retailer_logo,
    load_retailer_logo, reverse_geocode_location,
)
from .models import MonthlyUsage
from . import auth
from .rules import PREFERENCES, assess
from .throttle import QuotaUnavailable, client_id, hit

class PrivacyHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/shop-logo/'):
            response['Content-Security-Policy'] = "default-src 'none'; img-src 'none'; style-src 'none'; sandbox"
            response['Cache-Control'] = 'public, max-age=86400, immutable'
        else:
            response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response['Permissions-Policy'] = 'camera=(self), microphone=(), geolocation=(self)'
        if not request.path.startswith(settings.STATIC_URL) and not request.path.startswith('/api/shop-logo/'):
            response['Cache-Control'] = 'no-store, private'
        return response

@ensure_csrf_cookie
@require_GET
def index(request):
    if settings.AUTH_REQUIRED and not auth.unlocked(request):
        return auth.login_page(request)
    return render(request, 'scanner/index.html')

@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})

@require_GET
def shop_logo(request, code):
    if code not in RETAILERS:
        return HttpResponse(status=404)
    try:
        content, content_type = load_retailer_logo(code)
        source = 'catalogue'
    except (ShopSearchError, ValueError, ImportError):
        content, content_type = fallback_retailer_logo(code)
        source = 'fallback'
    response = HttpResponse(content, content_type=content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-FoodLens-Logo-Source'] = source
    response['Content-Disposition'] = f'inline; filename="{code}-logo"'
    return response

@require_POST
def location_name(request):
    try:
        lat = float(request.POST.get('lat', ''))
        lon = float(request.POST.get('lon', ''))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Share a valid current location.'}, status=400)
    if not (50.5 <= lat <= 53.7 and 3.0 <= lon <= 7.7):
        return JsonResponse({'error': 'Current location must be within the Netherlands.'}, status=400)
    name = reverse_geocode_location(round(lat, 3), round(lon, 3))
    if not name:
        return JsonResponse({'error': 'The current location name could not be found. Enter a city instead.'}, status=503)
    return JsonResponse({'location_name': name})

@require_GET
def config(request):
    legacy_access=bool(settings.SCANNER_ACCESS_CODE) and not settings.AUTH_REQUIRED
    return JsonResponse({'ai_configured': True,
        'access_required': legacy_access,
        'unlocked': not legacy_access or bool(request.session.get('unlocked')),
        'authenticated': auth.unlocked(request) if settings.AUTH_REQUIRED else True,
        'auth_required': settings.AUTH_REQUIRED,
        'model': settings.GEMINI_MODEL if settings.GEMINI_API_KEY else 'tesseract-local',
        'scan_provider': 'Gemini Flash-Lite' if settings.GEMINI_API_KEY else 'Private local OCR (free)', 'max_bytes': MAX_BYTES})

@require_GET
def usage(request):
    user=auth.account(request)
    if settings.AUTH_REQUIRED and not auth.unlocked(request):return JsonResponse({'error':'Unlock the app first.'},status=401)
    rows=MonthlyUsage.objects.filter(account=user,month=date.today().replace(day=1)) if user else MonthlyUsage.objects.none()
    totals=rows.aggregate(scans=Sum('scans'),input=Sum('input_tokens'),output=Sum('output_tokens'))
    input_tokens=totals['input'] or 0;output_tokens=totals['output'] or 0
    usd=input_tokens/1_000_000*0.10+output_tokens/1_000_000*0.40
    return JsonResponse({'month':date.today().strftime('%B %Y'),'scans':totals['scans'] or 0,
        'input_tokens':input_tokens,'output_tokens':output_tokens,'estimated_usd':round(usd,6),
        'estimated_inr':round(usd*settings.USD_TO_INR_RATE,4),'usd_to_inr_rate':settings.USD_TO_INR_RATE,
        'model':settings.GEMINI_MODEL if settings.GEMINI_API_KEY else 'Tesseract local OCR · free'})

@require_POST
def shop_search(request):
    if settings.AUTH_REQUIRED and not auth.unlocked(request):
        return JsonResponse({'error': 'Sign in and unlock the app first.'}, status=401)
    if not settings.AUTH_REQUIRED and settings.SCANNER_ACCESS_CODE and not request.session.get('unlocked'):
        return JsonResponse({'error': 'Enter your private-beta access code before comparing prices.'}, status=403)
    try:
        if (not hit('shop-search:' + client_id(request), settings.SHOP_SEARCHES_PER_HOUR, 3600)
                or not hit('shop-search-daily-total', settings.SHOP_SEARCHES_PER_DAY, 86400)):
            return JsonResponse({'error': 'Shopping search limit reached. Please try again later.'}, status=429)
        raw_lat, raw_lon = request.POST.get('lat', '').strip(), request.POST.get('lon', '').strip()
        if bool(raw_lat) != bool(raw_lon):
            return JsonResponse({'error': 'Share both latitude and longitude, or enter a Dutch city.'}, status=400)
        result = build_shop_search(
            request.POST.get('query', ''), request.POST.get('preference', 'vegetarian_no_eggs'),
            settings.GEMINI_API_KEY, settings.GEMINI_MODEL,
            lat=float(raw_lat) if raw_lat else None, lon=float(raw_lon) if raw_lon else None,
            location_text=request.POST.get('location', ''),
        )
        input_tokens = result.pop('input_tokens', 0)
        output_tokens = result.pop('output_tokens', 0)
        user = auth.account(request)
        if user and (input_tokens or output_tokens):
            row, _ = MonthlyUsage.objects.get_or_create(
                account=user, month=date.today().replace(day=1), model_name=settings.GEMINI_MODEL)
            MonthlyUsage.objects.filter(pk=row.pk).update(
                input_tokens=F('input_tokens') + input_tokens, output_tokens=F('output_tokens') + output_tokens)
        return JsonResponse(result)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except ShopSearchError as exc:
        return JsonResponse({'error': str(exc)}, status=503)
    except QuotaUnavailable:
        return JsonResponse({'error': 'Shopping search is temporarily unavailable.'}, status=503)

@require_POST
def unlock(request):
    try:
        if not hit('login:' + client_id(request), 8, 600):
            return JsonResponse({'error': 'Too many attempts. Try again in ten minutes.'}, status=429)
    except QuotaUnavailable:
        return JsonResponse({'error': 'Access service is temporarily unavailable.'}, status=503)
    submitted = request.POST.get('code', '')
    if len(submitted) > 256 or (settings.SCANNER_ACCESS_CODE and not hmac.compare_digest(submitted.encode(), settings.SCANNER_ACCESS_CODE.encode())):
        return JsonResponse({'error': 'That access code did not match.'}, status=403)
    request.session.cycle_key()
    request.session['unlocked'] = True
    return JsonResponse({'unlocked': True})

@require_POST
def logout(request):
    request.session.flush()
    return JsonResponse({'unlocked': False})

def output(label, preference, example=False, provider='Gemini', extraction_confidence=None):
    assessment = assess(label, preference)
    if extraction_confidence is not None:
        assessment['confidence'] = min(assessment['confidence'],
            max(25, min(98, round(float(extraction_confidence)))))
    return {'label': label.model_dump(), 'assessment': assessment,
        'is_demo': example, 'provider': 'fictional example' if example else provider}

@require_POST
def scan(request):
    if settings.AUTH_REQUIRED and not auth.unlocked(request):return JsonResponse({'error':'Sign in and unlock the app first.'},status=401)
    if not settings.AUTH_REQUIRED and settings.SCANNER_ACCESS_CODE and not request.session.get('unlocked'):
        return JsonResponse({'error': 'Enter your private-beta access code before scanning.'}, status=403)
    try:
        if not hit('upload:' + client_id(request), settings.SCANS_PER_MINUTE * 3, 60):
            return JsonResponse({'error': 'Too many uploads. Please wait a minute.'}, status=429)
        if int(request.META.get('CONTENT_LENGTH') or 0) > MAX_BYTES + 65536:
            return JsonResponse({'error': 'Choose a photo smaller than 8 MB.'}, status=413)
        preference = request.POST.get('preference', 'vegetarian_no_eggs')
        if preference not in PREFERENCES:
            return JsonResponse({'error': 'Choose a valid dietary preference.'}, status=400)
        if request.POST.get('consent') != 'yes':
            return JsonResponse({'error': 'Consent is required before sending the label photo to the AI provider.'}, status=400)
        photo = request.FILES.get('photo')
        if not photo:
            return JsonResponse({'error': 'Take or upload a photo of the ingredients panel.'}, status=400)
        if photo.size > MAX_BYTES:
            return JsonResponse({'error': 'Choose a photo smaller than 8 MB.'}, status=413)
        cleaned = prepare_image(photo.read(MAX_BYTES + 1))
        # Global daily quota cannot be bypassed by a fresh browser session or new IP.
        if not hit('scan:' + client_id(request), settings.SCANS_PER_MINUTE, 60) or not hit('daily-total', settings.SCANS_PER_DAY, 86400):
            return JsonResponse({'error': 'Scan limit reached. Please try later.'}, status=429)
        result = extract_label(cleaned, settings.GEMINI_API_KEY, settings.GEMINI_MODEL) if settings.GEMINI_API_KEY else extract_label_local(cleaned)
        label = getattr(result,'label',result)
        user=auth.account(request)
        if user:
            row,_=MonthlyUsage.objects.get_or_create(account=user,month=date.today().replace(day=1),model_name=getattr(result,'model_name','') or settings.GEMINI_MODEL)
            MonthlyUsage.objects.filter(pk=row.pk).update(scans=F('scans')+1,input_tokens=F('input_tokens')+getattr(result,'input_tokens',0),output_tokens=F('output_tokens')+getattr(result,'output_tokens',0))
        return JsonResponse(output(label, preference, provider=getattr(result,'provider','Gemini'),
            extraction_confidence=getattr(result, 'confidence', None)))
    except ImageInputError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except ProviderError as exc:
        return JsonResponse({'error': str(exc)}, status=502)
    except QuotaUnavailable:
        return JsonResponse({'error': 'Quota service unavailable. Scanning is temporarily paused.'}, status=503)
    except (ValueError, OverflowError):
        return JsonResponse({'error': 'Invalid request.'}, status=400)

@require_GET
def example(request, name):
    preference = request.GET.get('preference', 'vegetarian_no_eggs')
    if name not in EXAMPLES or preference not in PREFERENCES:
        return JsonResponse({'error': 'Example or preference not found.'}, status=404)
    return JsonResponse(output(demo_label(name), preference, example=True))
