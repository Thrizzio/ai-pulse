import os

# Load .env if present (very small loader, no extra dependency)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    for line in open(_env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            val = v.strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1].strip()
            os.environ.setdefault(k.strip(), val)


def _clean_env(name: str, default: str = "") -> str:
    v = os.getenv(name, default).strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1].strip()
    return v


SECRET_KEY = _clean_env("SECRET_KEY", "ai-pulse-dev-secret")
DATABASE_URL = _clean_env("DATABASE_URL", "sqlite:///./aipulse.db")
AI_MODE = _clean_env("AI_MODE", "mock")  # "mock" or "live"
LLM_API_URL = _clean_env("LLM_API_URL", "")
LLM_API_KEY = _clean_env("LLM_API_KEY", "")
LLM_MODEL = _clean_env("LLM_MODEL", "")
TOKEN_HOURS = 12
EXPANDED_SEED = _clean_env("EXPANDED_SEED", "false").lower() in ("true", "1", "yes")
