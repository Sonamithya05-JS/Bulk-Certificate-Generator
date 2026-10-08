# Bulk Certificate Generator API

## 1. Project Overview

A backend-only REST API that generates PDF certificates **in bulk**. A client sends **one** request containing an event name, a date and a list of recipients. The API immediately returns a job ID, then creates one PDF certificate per recipient **in the background**. The client can check progress at any time and download the certificates.

Typical use: an organisation finishes a workshop and needs certificates for 100+ participants.

## 2. Features

- One request for many recipients (no "one API call per certificate")
- Strict input validation with clear `422` error messages (Pydantic)
- Background processing (`FastAPI BackgroundTasks`) – the API responds instantly
- One professional, predefined landscape A4 certificate design (ReportLab)
- **Per-certificate status** – one failure never stops the rest of the job
- Live job progress (`successful_count`, `failed_count`, `progress_percentage`)
- Job-level status: `PROCESSING`, `COMPLETED`, `COMPLETED_WITH_ERRORS`, `FAILED`
- Safe filenames + path-traversal protection
- Automatic database table creation
- Swagger UI documentation
- 62 automated tests

## 3. Technology Stack

| Purpose | Technology |
|---|---|
| Language | Python 3.11+ |
| Web framework | FastAPI (+ Uvicorn server) |
| Database | SQLite |
| ORM | SQLAlchemy 2.x |
| Validation | Pydantic v2 (`EmailStr` via `email-validator`) |
| PDF generation | ReportLab |
| Tests | Pytest + FastAPI `TestClient` |

## 4. Project Structure

```
bulk-certificate-generator/
├── app/
│   ├── main.py                    # FastAPI app, startup, error handlers, /health
│   ├── config.py                  # Settings from environment variables
│   ├── api/
│   │   ├── jobs.py                # POST /api/jobs/, GET job status, GET job certificates
│   │   └── certificates.py        # GET /api/certificates/{id}/  (download PDF)
│   ├── database/
│   │   ├── database.py            # Engine, session factory, get_db dependency
│   │   └── models.py              # GenerationJob and Certificate tables
│   ├── schemas/
│   │   └── job.py                 # Pydantic request/response models + validation
│   ├── services/
│   │   ├── certificate_generator.py  # Creates ONE PDF (no database knowledge)
│   │   └── job_processor.py          # Creates jobs + background loop over recipients
│   └── utils/
│       └── validators.py          # Text cleaning, safe filenames, path check
├── templates/
│   └── certificate_template.py    # The single certificate design (layout, fonts, colours)
├── generated_certificates/        # PDFs are stored here (git-ignored, .gitkeep kept)
├── tests/                         # 62 tests (+ conftest.py with shared fixtures)
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
├── run.py                         # Starts the server
└── README.md
```

## 5. Setup Instructions

Requirements: **Python 3.11 or newer**.

### Create a virtual environment

```bash
cd bulk-certificate-generator

# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
venv\Scripts\Activate.ps1
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### (Optional) Configure environment variables

The app works without any configuration. To change defaults:

```bash
cp .env.example .env     # Windows: copy .env.example .env
```

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<project>/bulk_certificates.db` | Database location |
| `CERTIFICATES_DIR` | `generated_certificates` | Where PDFs are stored |
| `MAX_RECIPIENTS_PER_JOB` | `1000` | Max recipients per request |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Used by `run.py` |

## 6. Running the Application

```bash
python run.py
```

(or: `uvicorn app.main:app --reload`)

On startup the database tables and the certificates folder are created automatically.

- API base URL: `http://127.0.0.1:8000`
- **Swagger UI: http://127.0.0.1:8000/docs**
- ReDoc: http://127.0.0.1:8000/redoc

## 7. Running Tests

```bash
pytest
```

Expected: `62 passed`. (A harmless `httpx` deprecation warning from Starlette may be shown.)

Tests never need a running server. Every test uses its own temporary SQLite database and temporary certificates folder, so your real data is never touched.

| Test file | What it covers |
|---|---|
| `test_jobs.py` | Creating a job, unique IDs, 100-recipient bulk request, `/health` |
| `test_validation.py` | Empty/invalid name, email, date, event, recipients; helper functions |
| `test_certificate_generation.py` | Real PDF files, safe names, duplicates, unsupported characters |
| `test_job_status.py` | Completed job, in-progress percentage, unknown job |
| `test_failure_handling.py` | One failure doesn't stop others, all-fail → `FAILED`, crash handling |
| `test_certificate_retrieval.py` | Listing, PDF download, 404/409 cases, missing file, path traversal |

## 8. API Documentation

| Method | Endpoint | Description | Success code |
|---|---|---|---|
| `GET` | `/health` | Health check | 200 |
| `POST` | `/api/jobs/` | Create a bulk generation job | **202 Accepted** |
| `GET` | `/api/jobs/{job_id}/` | Job status and progress | 200 |
| `GET` | `/api/jobs/{job_id}/certificates/` | List certificates of a job | 200 |
| `GET` | `/api/certificates/{certificate_id}/` | Download one PDF | 200 |

**Error codes:** `404` unknown job/certificate or missing PDF file · `409` certificate failed or is not ready yet · `422` invalid input · `500` database error (generic message, details only in server logs).

### 8.1 Create a job (submit a bulk request)

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "Python Workshop",
    "certificate_date": "2026-10-08",
    "recipients": [
      {"name": "Sona Mithya", "email": "sona@example.com"},
      {"name": "Priya", "email": "priya@example.com"}
    ]
  }'
```

Response (`202 Accepted`):

```json
{
  "job_id": "0847f9c1d56e43d09558f8c383710e99",
  "status": "PROCESSING",
  "total_recipients": 2
}
```

Validation rules: `event_name` not empty (max 150 chars) · `certificate_date` a real date `YYYY-MM-DD` · `recipients` at least 1 (max `MAX_RECIPIENTS_PER_JOB`) · each `name` not empty (max 80 chars) · each `email` a valid email address.

Example validation error (`422`):

```json
{
  "detail": "Invalid request data",
  "errors": [
    {"field": "event_name", "message": "event_name must not be empty"},
    {"field": "recipients.0.email", "message": "value is not a valid email address: An email address must have an @-sign."}
  ]
}
```

> If any recipient is invalid, the **whole request is rejected** and nothing is saved. This gives the client a clear "fix and resend" signal. Failures that happen *during generation* are handled per recipient (see section 11).

### 8.2 Check job status

```bash
curl http://127.0.0.1:8000/api/jobs/<job_id>/
```

While processing:

```json
{
  "job_id": "0847f9c1d56e43d09558f8c383710e99",
  "event_name": "Python Workshop",
  "status": "PROCESSING",
  "total_recipients": 100,
  "successful_count": 65,
  "failed_count": 2,
  "completed_count": 67,
  "progress_percentage": 67,
  "created_at": "2026-10-08T04:26:15.228380",
  "completed_at": null
}
```

After completion (some failures):

```json
{
  "job_id": "0847f9c1d56e43d09558f8c383710e99",
  "event_name": "Python Workshop",
  "status": "COMPLETED_WITH_ERRORS",
  "total_recipients": 100,
  "successful_count": 95,
  "failed_count": 5,
  "completed_count": 100,
  "progress_percentage": 100,
  "created_at": "2026-10-08T04:26:15.228380",
  "completed_at": "2026-10-08T04:26:15.264553"
}
```

Timestamps are in **UTC**. `completed_count = successful_count + failed_count`.

### 8.3 Retrieve certificates

List all certificates of a job:

```bash
curl http://127.0.0.1:8000/api/jobs/<job_id>/certificates/
```

```json
{
  "job_id": "0847f9c1d56e43d09558f8c383710e99",
  "certificates": [
    {
      "certificate_id": 1,
      "recipient_name": "Sona Mithya",
      "email": "sona@example.com",
      "status": "SUCCESS",
      "download_url": "/api/certificates/1/",
      "error_message": null
    },
    {
      "certificate_id": 2,
      "recipient_name": "சோனா",
      "email": "tamil@example.com",
      "status": "FAILED",
      "download_url": null,
      "error_message": "Recipient name contains characters the certificate font cannot display: ச ோ ன ா"
    }
  ]
}
```

Download one PDF:

```bash
curl -o sona.pdf http://127.0.0.1:8000/api/certificates/1/
```

Downloading a failed certificate returns `409` with the failure reason.

## 9. Bulk Processing Explained

1. `POST /api/jobs/` validates the request.
2. **In one database transaction** it saves one `GenerationJob` row and one `Certificate` row per recipient (status `PENDING`).
3. It schedules `process_job(...)` with FastAPI `BackgroundTasks` and **returns the job ID immediately** (`202 Accepted`). A 500-recipient request returned in about 0.06 seconds in testing.
4. After the response is sent, the background task loops over the recipients, generating one PDF each. After **every** certificate it commits, so `GET /api/jobs/{id}/` shows live progress.
5. When all recipients are done, the job gets its final status.

The background task opens its **own** database session, because the request's session is closed once the response has been sent.

## 10. Status Transitions

```
Job:          PROCESSING ──► COMPLETED               (0 failures)
                         ├─► COMPLETED_WITH_ERRORS   (some succeeded, some failed)
                         └─► FAILED                  (every certificate failed, or the job crashed)

Certificate:  PENDING ──► SUCCESS
                      └─► FAILED  (+ error_message)
```

Note on `PENDING` for jobs: it is a valid status (and the column default), but with `BackgroundTasks` the job starts working immediately, so new jobs are created directly as `PROCESSING`. `PENDING` would become meaningful with a queue-based worker (see Future Scope).

## 11. Failure Handling Explained

- Each recipient is processed inside its own `try/except`.
- If one certificate fails, **only that row** is marked `FAILED` with a useful `error_message`; the loop continues with the next recipient.
- Expected failures (`CertificateGenerationError`) show their message. **Unexpected** exceptions are logged with a stack trace on the server, but the API user only sees a generic message such as `Unexpected error while generating certificate (RuntimeError)` – no internals leak.
- A partially written PDF is deleted if generation fails.
- If the whole job crashes (e.g. database failure), the job is marked `FAILED` so it never stays `PROCESSING` forever while the server is running.

A **real** failure you can reproduce without any mocking: a recipient name written in a script that ReportLab's built-in fonts cannot display (Tamil, Chinese, emoji …). Such recipients are marked `FAILED` with a clear reason instead of getting a certificate full of broken glyphs, while everyone else still succeeds. Names with accents (`José Müller`) work fine.

## 12. Database Design

SQLite file `bulk_certificates.db`, tables created automatically on startup.

**`generation_jobs`**

| Column | Type | Notes |
|---|---|---|
| `id` | string (PK) | random UUID hex, e.g. `0847f9c1…` – hard to guess |
| `event_name` | string | |
| `certificate_date` | date | |
| `total_recipients` | int | |
| `successful_count` / `failed_count` | int | updated after each certificate |
| `status` | string | `PENDING/PROCESSING/COMPLETED/COMPLETED_WITH_ERRORS/FAILED` (indexed) |
| `created_at` / `completed_at` | datetime (UTC) | |

**`certificates`** (one row per recipient)

| Column | Type | Notes |
|---|---|---|
| `id` | int (PK) | the `certificate_id` in the API |
| `job_id` | FK → `generation_jobs.id` | indexed |
| `name`, `email` | string | |
| `status` | string | `PENDING/SUCCESS/FAILED` |
| `certificate_path` | string, nullable | **relative** to the certificates folder |
| `error_message` | text, nullable | why it failed |
| `created_at` | datetime (UTC) | |

Relationship: one job → many certificates. Improvement over the suggested schema: `certificate_path` is stored relative to the certificates folder, so moving the project or the folder never breaks old rows.

## 13. Certificate Generation Approach

- The design lives in **one** file: `templates/certificate_template.py` (page size, fonts, colours, positions). Changing the look = editing that file only.
- `app/services/certificate_generator.py` creates exactly one PDF: it validates the characters, builds a safe filename, draws the template and saves the file. It knows nothing about the database, which makes it easy to test.
- The recipient name is upper-cased, the date is printed as `DD-MM-YYYY`, long names shrink to fit and long event names wrap onto up to 3 lines.
- Files are stored as `generated_certificates/<job_id>/<safe_name>_certificate.pdf`, e.g. `generated_certificates/0847.../sona_mithya_certificate.pdf`. A per-job folder avoids clashes between jobs; two people with the same name in one job get `..._2_certificate.pdf`.

**Security / file handling**

- Filenames are built only from `[a-z0-9_]` (`../../etc/passwd` → `etc_passwd`).
- User input is never used as a path; only server-generated job IDs are used as folder names.
- On download the resolved path is checked to be **inside** the certificates folder (blocks path traversal even if a database row is tampered with – there is a test for this).
- `.gitignore` excludes `*.db`, `.env`, the virtual environment and all generated PDFs.

## 14. Important Design Decisions

| Decision | Why |
|---|---|
| **One endpoint for bulk** | The client sends all recipients at once; no per-certificate calls. |
| **`202 Accepted` + job ID** | The work is not finished when we respond, and `202` says exactly that. |
| **Reject the whole request if any recipient is invalid** | Simple, predictable; the client fixes the data and resends. Generation-time failures are tracked per recipient. |
| **Individual certificate status** | Needed to report "95 ok, 5 failed" and show *why* each failed. |
| **Continue after individual failures** | One bad record must not block 99 good ones. |
| **Commit after every certificate** | Live progress, and nothing is lost if the server stops mid-job. |
| **One predefined template** | Requirement; keeps the code small. The template is isolated in one file. |
| **Relative paths in the DB + path check on download** | Portable and safe. |
| **Dependency injection for DB session / folder / session factory** | Tests swap in a temporary database and folder without touching the real ones. |
| **Business logic in `services/`, HTTP in `api/`** | Endpoints stay tiny and easy to read. |

## 15. Why FastAPI?

- Built-in request validation through Pydantic type hints – less code than Flask, lighter than Django.
- Automatic Swagger docs at `/docs`.
- `BackgroundTasks` is built in, so no extra infrastructure is needed.
- Dependency injection makes database sessions and testing clean.
- Django would bring an admin, templates and auth we do not need for a small API-only service; plain Flask would need extra libraries for validation and docs.

## 16. Why SQLite?

- Zero setup: a single file, ships with Python – anyone can clone and run the project.
- Fully relational (foreign keys, indexes, transactions), which is what the assignment asks for.
- SQLAlchemy hides the database differences, so switching to PostgreSQL later means changing `DATABASE_URL`.
- Limitation: only one writer at a time and not meant for many servers. Fine for this project, not for heavy production traffic.

## 17. Why ReportLab?

- Pure Python, installs with `pip` – no external programs (unlike wkhtmltopdf/Chrome-based HTML→PDF).
- Precise control of layout, centring and fonts, and fast: hundreds of certificates take seconds.
- Built-in fonts keep PDFs small. Trade-off: built-in fonts only cover Western European characters (see Future Scope).

## 18. Why Background Processing (`BackgroundTasks`)?

- Generating 100+ PDFs can take seconds to minutes; HTTP clients should not wait that long (timeouts).
- The assignment says the client should get the job ID without waiting for every PDF.
- `BackgroundTasks` needs no extra services (no Redis, no worker), so it is easy to run and to explain.
- **Known limitation:** the tasks live inside the server process. If the server restarts while a job is running, that job stops and remains `PROCESSING`. For production use a real queue (Celery/RQ) – see Future Scope.

## 19. Learning Section (interview notes)

- **Request flow:** `POST /api/jobs/` → Pydantic validation → `create_job` saves job + recipients → `BackgroundTasks` schedules `process_job` → response `202` → loop generates PDFs and updates the database → client polls `GET /api/jobs/{id}/`.
- **Why a new session in the background task?** The request session closes after the response; sessions are also not thread-safe.
- **Why `check_same_thread=False` for SQLite?** FastAPI runs requests/tasks in different threads; each thread still uses its own session.
- **Why is progress rounded down?** So `100%` appears only when everything is really done.
- **How do tests simulate failure?** Either by monkeypatching `certificate_generator.generate_certificate_pdf` to raise for chosen names, or with a real Tamil name that the built-in font cannot draw.
- **Why do tests see a finished job right after `POST`?** Starlette's `TestClient` runs background tasks before returning the response.
- **Possible interview modifications:** change the date format (one line in `certificate_generator.py`), change the design (`certificate_template.py`), add a `ZIP` download endpoint, accept partial success on validation, add a `retry failed` endpoint.

## 20. Future Scope

- **PostgreSQL** instead of SQLite for concurrent writes and multi-server deployment (change `DATABASE_URL`, add Alembic migrations).
- **Celery / RQ + Redis** for large or long-running jobs, retries and surviving server restarts (this is also where `PENDING` becomes useful).
- **Cloud storage (S3)** for the PDFs, with signed download URLs.
- **Authentication / authorization** (API keys or OAuth) so each client only sees their own jobs.
- **Emailing** each certificate to the recipient.
- **ZIP download** of all certificates of a job.
- **Unicode fonts**: embed a TTF font (e.g. Noto Sans) so names in Tamil, Hindi, Chinese etc. work.
- Rate limiting, pagination of the certificates list for very large jobs, a "retry failed certificates" endpoint, unique certificate numbers / QR-code verification.
