# FoodLens · foodlabel-scanner

A standalone, mobile-first Django app for photographing Dutch food labels, translating visible text into English, and checking ingredient compatibility with vegan or vegetarian preferences.

**Repository:** `ghanshyam91-commits/foodlabel-scanner`. This is a standalone project, separate from DigiRobe and Eduvera. `main` holds the initial application; `stage` is the staging branch. No live AI key is included. Hosting and real photo scanning require separate configuration.

## What is included

- Camera capture / photo upload, preview, metadata stripping and image validation.
- Dutch-to-English text extraction and translation using a configurable Gemini model.
- Separate deterministic dietary rules applied to the **original** ingredient text.
- Vegan-compatible, vegetarian-not-vegan, non-vegetarian ingredient found, and uncertain results.
- Vegetarian without eggs, vegetarian with eggs, and vegan preferences.
- Ingredient explanations, original label transcription, full translation, separate “contains” / “may contain” sections.
- Explicit per-photo AI consent. Browser-local saved text results, only on demand. Photos are not saved.
- Clearly marked fictional examples that use the real rule engine, not the external AI service.
- Private-beta passcode, CSRF protection, security headers and shared production rate/cost quotas.
- Unit and integration tests, GitHub Actions, Docker and Railway configuration.

Not included: barcode lookup, recipe recognition, live text overlay on photos, multiple-photo merging, manufacturer certification verification, native iOS/Android binaries, or allergy-safety decisions.

## Run locally

Use Python 3.12 or a supported compatible Python version.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# For real photo scans, set GEMINI_API_KEY in .env.
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Local development is enabled by the supplied `.env.example`. Without an API key, the UI explicitly displays preview mode and only fictional examples work. No real scan is silently replaced by a demo.

The API key stays on the backend. Never put it in browser JavaScript, Git, an issue, or a chat message. Generate it using Google AI Studio and store it as a server environment variable. Provider availability, quota and billing must be checked for the actual account. The default model is `gemini-3.1-flash-lite`; `GEMINI_MODEL` is configurable.

## Tests

```bash
DJANGO_DEBUG=1 python manage.py check
DJANGO_DEBUG=1 python manage.py test scanner.tests --verbosity 2
```

Core tests can also run without Django installed, provided Pillow, Pydantic and HTTPX are installed:

```bash
python -m unittest scanner.tests.test_rules scanner.tests.test_images scanner.tests.test_provider -v
```

See `docs/VALIDATION.md` for what was actually executed when this package was prepared. Mocked provider tests do **not** prove live extraction accuracy. Before production, benchmark real Dutch labels, including curved, blurred, multilingual, compound-ingredient and allergen-warning cases; manually verify each output.

## GitHub workflow

This repository contains only FoodLens. Work on `stage` for staging changes; promote reviewed changes to `main`. Tests run on pushes and pull requests through GitHub Actions.

```bash
git clone https://github.com/ghanshyam91-commits/foodlabel-scanner.git
cd foodlabel-scanner
git switch stage
```

Never commit `.env`, photos, access codes or provider API keys. The optional `scripts/publish.sh` is for creating a *different, fresh* private repository from a standalone copy; do not run it for this already-created repository.

## Deployment

The Dockerfile and `railway.json` are included, but **no deployment has been performed**.

In Railway, create a separate project/service from the new repository, select `stage` for staging, add Redis, then configure:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<random secret with at least 50 characters>
DJANGO_ALLOWED_HOSTS=<exact Railway/custom hostname>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<exact hostname>
GEMINI_API_KEY=<server-side API key>
GEMINI_MODEL=gemini-3.1-flash-lite
USD_TO_INR_RATE=90
SCANNER_ACCESS_CODE=<private passcode with at least 16 characters>
REDIS_URL=<Redis connection string>
TRUST_PROXY_SSL=1
SCANS_PER_MINUTE=5
SCANS_PER_DAY=100
```

Only set `TRUST_PROXY_SSL=1` behind a trusted HTTPS reverse proxy that removes spoofed forwarded headers. The `/health/` endpoint is exempt from HTTPS redirect for platform health checks. All normal production pages require HTTPS. Configure an ingress request-body limit of 9 MB and connection limits as additional protection.

Generate secrets locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Do not commit the output. Redis is required in production to keep daily paid-call quotas shared across workers/restarts. Cache failure blocks scanning. Failed AI requests count towards quota to prevent automatic retry storms. Quotas do not replace provider-side spend controls.

Signed-cookie sessions hold only the private-beta access flag. There is no account or server-side scan-history database. Rotating `DJANGO_SECRET_KEY` invalidates all existing sessions. Passcode rotation alone does not revoke already-unlocked cookies; rotate the signing key too when immediate revocation is needed. Use proper user accounts before a broader public launch.

## API

- `GET /api/config/`: non-secret configuration and access status.
- `POST /api/unlock/`: form field `code`; CSRF required.
- `POST /api/logout/`: clear access session; CSRF required.
- `POST /api/scan/`: multipart `photo`, `preference`, `consent=yes`; CSRF required.
- `GET /api/examples/{oats|chocolate|sweets|bread}/?preference=vegan`: clearly fictional examples.
- `GET /health/`: process health, not AI readiness.

## Important limits

An AI reading error can still cause a wrong result. “Vegan-compatible ingredients” is not a certification and cannot verify manufacturing aids. Unknown or missing ingredient text blocks positive results. Do not use this app for medical or allergy-safety decisions. See `docs/SAFETY.md` and `docs/PRIVACY.md`.

## Reference documentation

- Gemini model: https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite
- Gemini request and JSON schema contract: https://ai.google.dev/api/generate-content
- Django supported versions: https://www.djangoproject.com/download/
- V-Label explanations: https://www.v-label.com/faqs/
- Vegan Society on allergen versus vegan labelling: https://www.vegansociety.com/news/blog/TM2021/allergen-vs-vegan-labelling

References inform the implementation; FoodLens is not affiliated with or certified by those organizations. The starter vocabulary requires independent review and expansion before public reliance.
