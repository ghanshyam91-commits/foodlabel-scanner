# Validation record — 17 September 2026

## GitHub Actions: verified success

The full Tests workflow passed for application commit `ba30ff13b2c5b90ad5df78ab021f5f041fd02511` on the `stage` branch. The same application commit was published on `main`.

Run: https://github.com/ghanshyam91-commits/foodlabel-scanner/actions/runs/35146869784

Verified steps:

- Dependency installation succeeded on Python 3.12.14 with Django 5.2.17.
- `python manage.py check`: no issues.
- `python manage.py test scanner.tests --verbosity 2`: **83 tests passed**, including 69 core tests and 14 Django integration tests. The log reports `Ran 83 tests in 0.439s` and `OK`.
- `python manage.py collectstatic --noinput`: 4 static files copied and post-processed.

The Django integration tests use Django's test client. Provider responses are mocked; this successful workflow does not establish live AI accuracy, production Redis behavior, public HTTPS access or a deployed server. This documentation update does not change application code.

## Local and preparation checks

- 69 Python unit tests covering dietary rules, schema validation, image processing, and mocked provider responses. See `core-test-results.txt`.
- Python syntax compilation of all project modules.
- JavaScript syntax check with `node --check`.
- During package preparation, offline Chromium UI checks at 390 × 844 and 1440 × 1000: layout without horizontal overflow; four example outcomes; separate precautionary warnings; save/reopen text history; changing the next-scan preference; tab navigation; upload preview; required consent; clear no-key error; photo removal; no JavaScript runtime errors.
- Visual inspection of the mobile screenshot during package preparation.

## Exact UI test boundary

The browser rendered the actual HTML, CSS and JavaScript offline. API results came from precomputed fictional examples processed by the actual Python rule engine. Browser storage was represented by an in-memory storage fixture because the offline document did not have an application origin. These checks exercise frontend interactions, not real Django routing, cookie behavior, network transport, physical camera hardware or persistent localStorage across browser restarts.

## Not executed / not verified

- A real Gemini image request. No API key was provided or reused from another project.
- Real Dutch-product image accuracy or dietary expert review.
- A production Gunicorn server or Docker build, Railway deployment, public HTTPS access, Redis integration, physical iPhone/iPad Safari camera behavior or live spend enforcement.

## Repository publication checks

- Re-ran the 69 core tests before publishing the source: all passed.
- The user created `ghanshyam91-commits/foodlabel-scanner`; the repository was empty and was initialized through the connected GitHub tools.
- All 42 published files matched the locally checked application tree exactly. Both `main` and `stage` were initialized with the application commit named above.
- Local dependency installation could not resolve PyPI. The subsequent GitHub Actions run installed the requirements and successfully ran the full Django test suite as recorded above.
- Python compilation and JavaScript syntax checks passed again. The UI harness could not be rerun during publication because the current environment has no Playwright browser binary; the offline UI results above refer to package preparation.
- No API key was added, no live AI call was made, and no deployment was performed as part of publishing source.

## Release gate

This is an initial source implementation with passing automated tests, not a verified production release. Connect a server-side Gemini API key, configure Redis and beta access, verify the deployment and test real labels before relying on results. Review `SAFETY.md` and `PRIVACY.md`.

Optional UI reproduction: install Playwright and its Chromium browser, then run `python scripts/test_ui_offline.py`. Set `CHROMIUM_EXECUTABLE` only when using a locally installed compatible Chromium. This harness mocks API responses and browser storage as described above.
