"""
Test configuration.

Runs every test against a throw-away SQLite database and storage folder (previously the tests
wrote into the repository's invoshield.db), with the assistant in mock + offline mode so no
network, Meta account or API key is needed.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="invoshield-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ["LOCAL_STORAGE_DIR"] = os.path.join(_TMP, "storage")
os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:1"  # unreachable -> local storage fallback
os.environ["APP_ENV"] = "development"
os.environ["AGENT_CHANNEL_MODE"] = "mock"
os.environ["AGENT_LLM_PROVIDER"] = "offline"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["WHATSAPP_APP_SECRET"] = "test-app-secret"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test-verify-token"
os.environ["EMAIL_WEBHOOK_SECRET"] = "test-email-secret"
os.environ["AGENT_BUSINESS_NAME"] = "Sri Lakshmi Traders"
os.environ["AGENT_DEFAULT_ORGANIZATION"] = "Apex FinTech Audits"
