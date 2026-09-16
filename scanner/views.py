import hmac
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from .demo import EXAMPLES, demo_label
from .images import MAX_BYTES, ImageInputError, prepare_image
from .provider import ProviderError, extract_label
from .rules import PREFERENCES, assess
from .throttle import QuotaUnavailable, client_id, hit

class PrivacyHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response['Permissions-Policy'] = 'camera=(self), microphone=(), geolocation=()'
        if not request.path.startswith(settings.STATIC_URL):
            response['Cache-Control'] = 'no-store, private'
        return response

@ensure_csrf_cookie
@require_GET
def index(request):
    return render(request, 'scanner/index.html')

@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})

@require_GET
def config(request):
    return JsonResponse({'ai_configured': bool(settings.GEMINI_API_KEY),
        'access_required': bool(settings.SCANNER_ACCESS_CODE),
        'unlocked': not settings.SCANNER_ACCESS_CODE or bool(request.session.get('unlocked')),
        'max_bytes': MAX_BYTES})

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

def output(label, preference, example=False):
    return {'label': label.model_dump(), 'assessment': assess(label, preference),
        'is_demo': example, 'provider': 'fictional example' if example else 'Gemini'}

@require_POST
def scan(request):
    if settings.SCANNER_ACCESS_CODE and not request.session.get('unlocked'):
        return JsonResponse({'error': 'Enter your private-beta access code before scanning.'}, status=403)
    if not settings.GEMINI_API_KEY:
        return JsonResponse({'error': 'Photo scanning is not configured yet. The owner must add GEMINI_API_KEY. You can try the labelled examples.'}, status=503)
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
        label = extract_label(cleaned, settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
        return JsonResponse(output(label, preference))
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
