# FoodLens

I started FoodLens to answer a fairly ordinary question while shopping in the Netherlands: *can I eat this, and where nearby can I buy it?* Packaging is often in Dutch, and the ingredient that matters can be buried in small print. The app reads a photo of the ingredients panel, translates what it can, and checks it against a vegetarian or vegan preference. It also has a separate supermarket search.

This is a Django project and an evolving personal tool. A green result means the **visible ingredients** passed the current rules. It is not a manufacturer certification, an allergen assessment, or a guarantee about cross-contact.

## What works today

- Take or upload a label photo. With a Gemini key, extraction and translation use Gemini; without one, the app uses local Tesseract OCR and a limited Dutch-to-English vocabulary. The latter requires the Tesseract executable and Dutch and English language data on the machine.
- Apply deterministic ingredient rules *after* reading the label. Results distinguish vegan-compatible, vegetarian, non-vegetarian and uncertain cases; missing or unreadable ingredient text cannot produce a confident positive result.
- Choose vegan, vegetarian with eggs, or vegetarian without eggs. Review the original text, translated ingredients and separate “contains” / “may contain” information.
- Search nearby Dutch supermarkets, compare catalogue prices, and keep a browser-local shopping list. Prices are snapshots; store availability is not guaranteed.
- Sign in with Google and unlock with a four-digit PIN when OAuth is configured. A temporary PIN path exists for development. The older private-beta access-code path is still present for deployments with account authentication disabled.
- View monthly scan/token counts and an *estimate* of AI cost in INR. The currency conversion is a configured display rate.

Photos are processed in memory and are not saved as files by the app. If Gemini is configured, an explicitly consented photo is sent to that provider. Saved shopping and scan text in the browser are separate from the server-side account and usage records. See [privacy](docs/PRIVACY.md) and [safety](docs/SAFETY.md).

## Try it locally

Python 3.12 is a good starting point. For local OCR, install the Tesseract executable with `eng` and `nld` trained data; `pytesseract` alone is not enough.

```bash
git clone https://github.com/ghanshyam91-commits/foodlabel-scanner.git
cd foodlabel-scanner
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/. The example `.env` enables local development. For real Gemini extraction, set `GEMINI_API_KEY` in `.env`. Without a key, real scans use local OCR; they do **not** silently switch to fictional examples. The examples route is separately marked as demo content. Google login requires both OAuth credentials and a matching callback configuration at `/auth/google/callback/`. In local development, account authentication is optional when `AUTH_REQUIRED=0`.

```bash
DJANGO_DEBUG=1 python manage.py check
DJANGO_DEBUG=1 python manage.py test scanner.tests
```

CI runs the tests in [GitHub Actions](.github/workflows/tests.yml). Provider tests use mocks, so they do not measure recognition accuracy on real packaging. [Validation notes](docs/VALIDATION.md) describe the earlier checks.

## How it is put together

`scanner/images.py` validates and prepares uploads. `scanner/provider.py` handles Gemini extraction; `scanner/local_ocr.py` handles the local fallback. `scanner/rules.py` makes the dietary decision from extracted text. `scanner/shop_search.py` combines catalogue products with nearby store locations. Django views enforce consent, authentication and quotas; Redis shares production quotas across workers. The UI is server-served HTML, CSS and JavaScript.

A deliberate split here is between *reading* and *deciding*. An AI response or OCR transcript is evidence to inspect, not the dietary rule itself. This makes rule behavior testable, though a bad transcript can still lead to a bad answer.

## Deployment notes

The repository has a Dockerfile and Railway configuration. For a real deployment, set `DJANGO_DEBUG=0`, a unique 50+ character `DJANGO_SECRET_KEY`, exact allowed hosts and CSRF origins, `DATABASE_URL`, `REDIS_URL`, and the chosen authentication variables. Set `GEMINI_API_KEY` only on the server. Tesseract and language data must also be present if you expect keyless scans. Run `python manage.py check --deploy` and verify the login and photo flow on the deployed service.

Do not copy the sample `.env` values into production. This is a prototype; catalogue coverage, OCR accuracy, auth configuration and provider costs need testing with real devices and labels before wider use.

## Known edges

Curved or blurry labels, nested ingredients and incomplete translations remain hard. “May contain” is kept separate from ingredients because precautionary allergen wording does not by itself establish whether a product is vegan. Prices may differ by branch or promotion. Product links are labelled as exact pages only when the app can verify them. Barcode lookup and manufacturer certification are not implemented.
