# AGENTS.md

## 🧠 Context & Architecture
This project is a **Serverless Web Application** where the "Backend" runs entirely inside the user's browser using **Pyodide (WASM)**.

### The Stack
1.  **Runtime:** Pyodide v0.25.0 (Python 3.11 in browser).
2.  **Backend Framework:** Django 4.x (running in-memory).
    * **Database:** SQLite (`:memory:`).
    * **Networking:** `pyodide-http` patches `requests` to use the browser's `Fetch API`.
    * **The Bridge:** There is **no localhost port**. We do not use `runserver`. Instead, JavaScript calls Python functions directly, and Python uses `django.test.Client` to route the request to a View.
3.  **Frontend:** HTML5 + Leaflet.js.

## ⚠️ Critical Constraints
1.  **No Subprocesses:** You cannot run `subprocess.Popen` or system shell commands.
2.  **No Sockets:** You cannot open TCP sockets (no Redis, no Postgres, no `runserver`).
3.  **Async/Sync:** Django runs in a synchronous manner, but Pyodide is async. We use `os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"` to allow DB access.
4.  **File System:** The file system is ephemeral (virtual RAM disk).
5.  **Imports:** External Python packages must be installed via `micropip.install()` in the JS bootstrap phase.

## 🛠️ Workflow for Code Changes
When asked to implement features:
1.  **Refactor First:** Do not keep all Python code in one giant template string. Suggest splitting the Python logic into a separate file (e.g., `backend.py`) that can be fetched or loaded into the Pyodide virtual file system.
2.  **The Bridge Pattern:** Always use the established pattern:
    * **JS:** `pyodide.runPython("handle_request('/api/path')")`
    * **Python:** Uses `django.test.Client().get('/api/path')` -> returns string/JSON.

## 🎯 Quality Standards
* Ensure `pyodide_http.patch_all()` is called before `django.setup()`.
* Handle `ModuleNotFoundError` by mocking the `base_app` module in `sys.modules` before Django boots.
* Always include error handling in Views (return `JsonResponse` with errors).
