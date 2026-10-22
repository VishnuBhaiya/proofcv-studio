# Backend development record

## 2026-09-06 — provider selection

User selected Gemini for the live AI provider. Implemented a Python standard-library
generateContent adapter with server-only configuration, JSON responses, conversation
and runtime-observation forwarding, sanitized errors and a 45-second timeout.
No implicit sample fallback. The final adapter performs explicit, bounded model rotation
for model-specific/retryable failures and stops early for shared configuration errors.

Verification: `.venv/Scripts/python.exe -m unittest server.test_gemini -v`
ran successfully: 6 tests, including parameterized HTTP 400/403/429/503 failures.
All network responses in these tests were mocked. No live model request was made.

Historical status above was the provider-only checkpoint. The app is now connected;
see ../DEVELOPMENT_RECORD.md for subsequent implementation and actual verification.

Configuration: edit the project-root `.env`, adding GEMINI_API_KEY and the exact
GEMINI_MODEL ID available in the user's AI Studio account. Never prefix the key
with VITE_, commit the private file, or put credentials into browser storage.
Having non-empty configuration is not proof that the connection works.

API reference checked: https://ai.google.dev/api/generate-content
