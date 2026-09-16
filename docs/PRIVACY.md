# Privacy and security notes

A photo is sent to the backend only when the user chooses “Read my label” and checks the AI consent box. The backend validates file contents, limits size/dimensions, removes EXIF metadata and sends a normalized JPEG to Google's Gemini API. Do not photograph faces, prescriptions, receipts with payment details, or other unnecessary personal data.

The application does not persist photo files or results in a database. Uploads are handled in process memory. Python objects are not cryptographically erased; hosting infrastructure and the external provider may have separate telemetry and retention. Provider data use depends on the paid/free service and account configuration. Review provider terms before launch; this project does not claim zero external retention.

Only the text result is saved in browser localStorage when the user taps Save scan. Up to 20 scans are retained on that browser profile until deleted. Dietary preference is also stored locally. Browser profiles may sync or be shared depending on device settings; FoodLens does not provide encrypted or account-isolated saved history.

The app uses a short-lived signed session cookie for private-beta access and a CSRF cookie. Client request IPs are HMACed for rate-limit keys; no raw photo or model response is deliberately logged. Hosting access logs may still contain client network data. Do not enable request-body logging in a proxy or APM tool.

No third-party frontend libraries, tracking scripts or external fonts are loaded. Model strings are rendered with textContent rather than HTML. The AI receives no browsing tools. API credentials remain in environment variables and are sent to the provider in a header, never a URL query string.

Production must use HTTPS, an exact host allowlist, trusted origins, a strong secret, a private-beta access code and Redis-backed shared quotas. Set an ingress body-size limit. Replace shared access codes with individual accounts and revocation before any public launch.
