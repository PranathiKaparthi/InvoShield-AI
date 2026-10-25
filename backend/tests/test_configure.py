"""Setup wizard helpers: .env merging, generated secrets and the WhatsApp credential check."""
import base64

import httpx

from scripts.configure import (check_whatsapp, merge_env, new_aes_key, new_jwt_secret, parse_env)


def test_merge_env_replaces_in_place_and_appends_missing():
    lines = ["# comment", "APP_ENV=development", "ANTHROPIC_API_KEY=", "APP_ENV=duplicate", "OTHER=1"]
    out = merge_env(lines, {"APP_ENV": "production", "ANTHROPIC_API_KEY": "sk-ant-x", "NEW_KEY": "v"})
    assert out[0] == "# comment" and out[1] == "APP_ENV=production" and "APP_ENV=duplicate" not in out
    values = parse_env(out)
    assert values == {"APP_ENV": "production", "ANTHROPIC_API_KEY": "sk-ant-x", "OTHER": "1", "NEW_KEY": "v"}


def test_generated_secrets_are_strong_and_valid():
    assert len(new_jwt_secret()) == 64 and new_jwt_secret() != new_jwt_secret()
    assert len(base64.b64decode(new_aes_key())) == 32  # AES-256


def test_whatsapp_check_reports_success_and_meta_errors():
    def ok_handler(request):
        assert request.headers["Authorization"] == "Bearer good"
        return httpx.Response(200, json={"verified_name": "Sri Lakshmi Traders", "display_phone_number": "+91 98000 00000"})

    good, msg = check_whatsapp("123", "good", "v21.0", httpx.Client(transport=httpx.MockTransport(ok_handler)))
    assert good and "Sri Lakshmi Traders" in msg

    def bad_handler(request):
        return httpx.Response(401, json={"error": {"message": "Invalid OAuth access token."}})

    good, msg = check_whatsapp("123", "bad", "v21.0", httpx.Client(transport=httpx.MockTransport(bad_handler)))
    assert not good and "Invalid OAuth" in msg


def test_gemini_model_listing_prefers_newest_stable_flash():
    from scripts.configure import gemini_models

    def handler(request):
        return httpx.Response(200, json={"models": [
            {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3-flash-preview", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
        ]})
    good, models, _ = gemini_models("AIza", httpx.Client(transport=httpx.MockTransport(handler)))
    assert good and models[0] == "gemini-2.5-flash" and "gemini-2.5-flash-lite" not in models
