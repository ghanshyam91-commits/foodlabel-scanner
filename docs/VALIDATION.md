# Validation record — 17 September 2026

## Executed successfully

- 69 Python unit tests covering dietary rules, schema validation, image processing, and mocked provider responses. See `core-test-results.txt`.
- Python syntax compilation of all project modules.
- JavaScript syntax check with `node --check`.
- Offline Chromium UI checks at 390 × 844 and 1440 × 1000: layout without horizontal overflow; four example outcomes; separate precautionary warnings; save/reopen text history; changing the next-scan preference; tab navigation; upload preview; required consent; clear no-key error; photo removal; no JavaScript runtime errors.
- Visual inspection of the mobile screenshot.

## Exact UI test boundary

The browser rendered the actual HTML, CSS and JavaScript offline. API results came from precomputed fictional examples processed by the actual Python rule engine. Browser storage was represented by an in-memory storage fixture because the offline document did not have an application origin. These checks exercise frontend interactions, not real Django routing, cookie behavior, network transport, physical camera hardware or persistent localStorage across browser restarts.

## Not executed / not verified

- Django integration tests and a complete Django server startup. Django was not installed in the preparation environment, and dependency download attempts were unavailable. The integration tests are included for CI or a configured development environment.
- A real Gemini image request. No API key was provided or reused from another project.
- Real Dutch-product image accuracy or dietary expert review.
- Docker build, Railway deployment, public HTTPS access, Redis integration, physical iPhone/iPad Safari camera behavior or live spend enforcement.
- GitHub Actions execution must be checked against the actual commit on GitHub; local unit results do not establish a remote CI result.

## Repository publication checks

- Re-ran the 69 core tests before publishing the source: all passed.
- The user created `ghanshyam91-commits/foodlabel-scanner`; the repository was empty and was initialized through the connected GitHub tools.
- Dependency installation was attempted again, but this environment could not resolve PyPI. Django integration tests remain unverified locally.
- Python compilation and JavaScript syntax checks passed again. The UI harness could not be rerun during publication because the current environment has no Playwright browser binary; the offline UI results above refer to package preparation.
- No API key was added, no live AI call was made, and no deployment was performed as part of publishing source.

## Release gate

This is an initial source implementation, not a verified production release. Install the requirements, run `python manage.py check` and `python manage.py test scanner.tests`, connect a server-side Gemini API key, configure Redis and beta access, and test real labels before deployment or reliance on results. Review `SAFETY.md` and `PRIVACY.md`.

Optional UI reproduction: install Playwright and its Chromium browser, then run `python scripts/test_ui_offline.py`. Set `CHROMIUM_EXECUTABLE` only when using a locally installed compatible Chromium. This harness mocks API responses and browser storage as described above.
