# Changes Log

## Change 1: Repository Hygiene, Secret Management, Python Pinning & Docker Entrypoint

### Plain Language Explanation
1. **Untracked `backend/.env`:**
   Previously, the local configuration file containing secret keys and credentials (`backend/.env`) was actively tracked in Git. This was a critical security flaw because any commit would leak secret keys to version control. The file has now been untracked from Git index so local environment secrets remain private on developer machines, while `.gitignore` ensures it stays ignored.
2. **Added `.env.example`:**
   Because `.env` is untracked, new developers need a clean template showing which environment variables the application expects. Created `.env.example` (with placeholders for `SECRET_KEY`, `DATABASE_URL`, `AI_MODE`, `LLM_API_URL`, `LLM_API_KEY`, and `LLM_MODEL`) without exposing actual secrets.
3. **Pinned Python 3.12 in `.python-version`:**
   Python 3.14 breaks dependency installation due to Pydantic/pydantic-core compilation incompatibilities. Creating `.python-version` containing `3.12` ensures development environments, version managers (`pyenv`, `mise`, `asdf`), and CI tools automatically use the tested, stable Python 3.12 runtime.
4. **Fixed Dockerfile CMD:**
   The backend code lives inside the `app/` subfolder (entrypoint `app/main.py`). The Dockerfile previously had `CMD ["uvicorn", "main:app", ...]`, which failed at runtime because `/app/main.py` does not exist inside the container. It has been corrected to `CMD ["uvicorn", "app.main:app", ...]`.

---

### Before vs. After

| Item | Before | After |
|---|---|---|
| **Git Tracking of `backend/.env`** | `backend/.env` was tracked in Git (`git ls-files` returned `backend/.env`), risking credential leakage. | Untracked from Git index (`git rm --cached backend/.env`). Remains locally on disk and is ignored by `.gitignore`. |
| **Environment Template** | No `.env.example` existed in the repository. | Added `.env.example` and `backend/.env.example` with non-secret template configuration keys. |
| **Python Version** | No `.python-version` file existed; unpinned Python versions caused build failures on Python 3.14. | Added `.python-version` pinning `3.12`. |
| **Dockerfile Entrypoint** | `CMD ["uvicorn", "main:app", ...]` crashed with `ModuleNotFoundError: Could not import module "main"`. | `CMD ["uvicorn", "app.main:app", ...]` correctly targets the `app` package. |

---

### Git Diff

```diff
diff --git a/backend/.env b/backend/.env
deleted file mode 100644
index 518f4a3..0000000
--- a/backend/.env
+++ /dev/null
@@ -1,6 +0,0 @@
-SECRET_KEY=pulse-7f3a9c2e1b-prod
-DATABASE_URL=sqlite:///./aipulse.db
-AI_MODE=mock
-LLM_API_URL=
-LLM_API_KEY=
-LLM_MODEL=

diff --git a/backend/Dockerfile b/backend/Dockerfile
index 1b1cb48..774b099 100644
--- a/backend/Dockerfile
+++ b/backend/Dockerfile
@@ -3,4 +3,4 @@ WORKDIR /app
 COPY . .
 RUN pip install -r requirements.txt
 EXPOSE 8000
-CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
+CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

--- /dev/null
+++ b/.python-version
@@ -0,0 +1 @@
+3.12

--- /dev/null
+++ b/.env.example
@@ -0,0 +1,6 @@
+SECRET_KEY=dev-secret-change-in-production
+DATABASE_URL=sqlite:///./aipulse.db
+AI_MODE=mock
+LLM_API_URL=
+LLM_API_KEY=
+LLM_MODEL=

--- /dev/null
+++ b/backend/.env.example
@@ -0,0 +1,6 @@
+SECRET_KEY=dev-secret-change-in-production
+DATABASE_URL=sqlite:///./aipulse.db
+AI_MODE=mock
+LLM_API_URL=
+LLM_API_KEY=
+LLM_MODEL=
```

---

### Verification
Tests in `backend/tests/test_setup.py`:
- `test_python_version_pinned`: **PASSED**
- `test_env_example_exists`: **PASSED**
- `test_dockerfile_cmd_uses_app_main`: **PASSED**
- `test_backend_env_not_tracked_in_git`: **PASSED**

