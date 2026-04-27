# Backend Internal Developer Documentation

This document is the internal maintenance guide for backend engineers.

## 1. Project Overview And Environment Setup

### 1.1 Tech Stack

- Runtime: Python 3.11 (container baseline)
- Web framework: FastAPI
- ORM: SQLAlchemy 2.x
- Migration: Alembic
- Database: PostgreSQL
- Cache/state: Redis
- Auth: JWT (access + refresh)
- Test: Pytest + FastAPI TestClient

### 1.2 Source Layout

```text
app/
  core/
    config.py          # env-driven settings
    exceptions.py      # custom HTTP exceptions
    logging.py         # logging setup
  database/
    connection.py      # SQLAlchemy engine/session/base
    redis.py           # singleton redis client + helpers
  models/
    user.py            # SQLAlchemy user model
    audit_log.py       # SQLAlchemy audit log model
  schemas/
    user.py            # pydantic request/response DTOs
  services/
    user_service.py    # user business logic
    auth_service.py    # token/session/login-attempt logic
    audit_service.py   # PostgreSQL audit log writer
    email_service.py   # switchable email providers
  routers/
    auth.py            # HTTP endpoints
main.py                # FastAPI app bootstrap + middleware + events
migrations/
  env.py               # Alembic runtime integration
  versions/
    0001_initial_users_table.py
tests/
  conftest.py
  test_auth.py
  test_migration.py
```

### 1.3 Local Environment Setup

1. Create venv using Python 3.11 or 3.12.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Start PostgreSQL and Redis.
5. Start app.

Commands:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env

docker compose up -d postgres redis
uvicorn main:app --reload --host 0.0.0.0 --port 18000
```

Containerized full stack:

```bash
docker compose up -d
```

### 1.4 Required Environment Variables

- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`

Important optional variables:

- `ALGORITHM` (default `HS256`)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30)
- `REFRESH_TOKEN_EXPIRE_DAYS` (default 7)
- `MAX_LOGIN_ATTEMPTS` (default 5)
- `LOCKOUT_DURATION_SECONDS` (default 900)
- `SESSION_EXPIRE_SECONDS` (default 86400)
- `MAX_PASSWORD_LENGTH` (default 72 bytes for bcrypt safety)

## 2. Runtime Architecture

### 2.1 Request Path

1. Request enters FastAPI in `main.py`.
2. Logging middleware records method/path/status/latency.
3. Router dispatches endpoint in `app/routers/auth.py`.
4. Endpoint calls service layer (`UserService`, `AuthService`).
5. Service layer reads/writes PostgreSQL and Redis.
6. Response model serializes response schema.

### 2.2 Layer Responsibilities

- Router layer:
- HTTP contract only
- request dependency wiring
- response model typing

- Service layer:
- business rules
- cross-resource operations
- consistency and side effects

- Database/cache adapters:
- SQLAlchemy session lifecycle
- Redis primitive operations + key design

- Schema/model layer:
- Pydantic request/response validation
- SQLAlchemy table structure

## 3. Database Schema

Current relational schema has one primary business table.

### 3.1 users Table

| Column | Type | Nullable | Constraints / Meaning |
|---|---|---|---|
| id | Integer | No | Primary key, indexed |
| email | String(255) | No | Unique + indexed |
| username | String(100) | No | Unique + indexed |
| hashed_password | String(255) | No | bcrypt hashed secret |
| full_name | String(255) | Yes | Optional profile field |
| is_active | Boolean | Yes (default true) | Account enabled/disabled flag |
| is_verified | Boolean | Yes (default false) | Reserved verification state |
| created_at | DateTime | No | default current timestamp |
| updated_at | DateTime | No | default current timestamp, auto-update |
| last_login_at | DateTime | Yes | last successful login timestamp |

Indexes from migration:

- `ix_users_id`
- `ix_users_email` (unique)
- `ix_users_username` (unique)
- `ix_users_is_active`

### 3.2 Migration Baseline

- Initial revision: `0001_initial_users_table`
- Alembic metadata is loaded from SQLAlchemy `Base.metadata` in `migrations/env.py`.

Upgrade/downgrade examples:

```bash
alembic upgrade head
alembic downgrade -1
```

## 4. Redis Data Model

Redis keys used by current implementation:

- `session:<session_id>` -> `<user_id>` (TTL = `SESSION_EXPIRE_SECONDS`)
- `login_attempts:<user_id>` -> integer counter (TTL = `LOCKOUT_DURATION_SECONDS`)
- `blacklist:<token>` -> `true` (TTL based on token lifetime)
- `cache:<key>` -> JSON blob (generic helper, not heavily used in current auth routes)
- `email_code:register:<email>` -> 6-digit verification code (TTL = `EMAIL_VERIFICATION_CODE_TTL_SECONDS`)
- `email_code:password_reset:<email>` -> 6-digit reset code (TTL = `PASSWORD_RESET_CODE_TTL_SECONDS`)

Operational implications:

- Account lockout is purely Redis-driven and auto-expires.
- Logout invalidation is blacklist-based; token lifetime controls blacklist TTL.
- Redis flush removes lockout and blacklist states.

## 5. API Design Rules And Current Endpoint Logic

All endpoints are under `/api/v1/auth`.

### 5.1 Register: `POST /register`

- Validates request schema.
- Checks email/username uniqueness.
- Hashes password with bcrypt.
- Creates user row.
- Returns `UserResponse`.

### 5.2 Login: `POST /login`

- Retrieves user by email.
- Checks lockout counter in Redis.
- Validates password and active status.
- Requires `user.is_verified == true`.
- Clears login-attempt counter on success.
- Updates `last_login_at`.
- Returns access/refresh tokens + user.

Failure flow:

- Invalid credentials increment `login_attempts:<user_id>`.
- At threshold, raises `429 AccountLockedException`.

### 5.3 Current User: `GET /me`

- Requires bearer token.
- Decodes JWT with token type `access`.
- Rejects blacklisted tokens.
- Loads user by ID from database.

### 5.4 Refresh: `POST /refresh`

- Receives refresh token in body.
- Rejects if token is blacklisted.
- Decodes token with expected type `refresh`.
- Issues new access token.

### 5.5 Logout: `POST /logout`

- Requires access bearer token header.
- Requires refresh token in body.
- Blacklists both access + refresh tokens in Redis.

Important implementation note:

- Effective auth invalidation behavior is token blacklist.
- Session helper methods are available but are not the primary auth source of truth.

### 5.6 Error Contract

Custom exception mapping in `app/core/exceptions.py`:

- `401 InvalidCredentialsException`
- `401 InvalidTokenException`
- `401 TokenBlacklistedException`
- `404 UserNotFoundException`
- `400 UserAlreadyExistsException`
- `400 PasswordTooLongException`
- `429 AccountLockedException`
- `403` for missing bearer header comes from `HTTPBearer`

Unhandled exceptions are converted to `500 Internal server error` by global exception handler in `main.py`.

## 6. Security Internals

### 6.1 Password Hashing

- Uses bcrypt with rounds=12.
- Enforces max encoded password length (`MAX_PASSWORD_LENGTH`, default 72 bytes).
- Throws `PasswordTooLongException` on byte-length overflow.

### 6.2 JWT Payload

Access token payload fields:

- `sub`: user id
- `iat`: issued at unix timestamp
- `exp`: expiry unix timestamp
- `type`: `access`

Refresh token payload fields:

- same fields, `type` is `refresh`

### 6.3 Token Verification

`decode_token` validates signature, expiry, algorithm, and token type match.

## 7. API Documentation Generation And Maintenance

Swagger/OpenAPI generation is automatic via FastAPI.

Configuration source:

- App-level metadata in `main.py` (`title`, `version`, `description`)
- Router tags and paths in `app/routers/auth.py`
- Request/response schemas in `app/schemas/user.py`

Runtime docs endpoints:

- Swagger UI: `/docs`
- OpenAPI spec: `/openapi.json`

How to improve docs quality when changing API:

1. Add endpoint `summary` and `description` in route decorators.
2. Add `response_model` consistently.
3. Add field descriptions/examples in Pydantic `Field(...)`.
4. Add explicit `responses={...}` in route decorators for error docs.

## 8. Test Strategy And Commands

### 8.1 Current Test Coverage Areas

`tests/test_auth.py` covers:

- register success/failure
- login success/failure
- lockout after repeated failures
- get current user
- refresh token
- password hashing and long UTF-8 password rejection
- token create/decode

`tests/test_migration.py` covers:

- alembic upgrade/downgrade lifecycle
- users table creation/removal
- alembic version state

### 8.2 Test Runtime Model

- SQL tests use temporary SQLite test DB (`test.db`).
- Redis is flushed before/after each test via fixture.
- FastAPI dependency override injects test DB session.

### 8.3 Useful Commands

```bash
pytest tests/ -v
pytest tests/test_auth.py -v
pytest tests/test_migration.py -v
pytest tests/ --cov=app --cov-report=term --cov-report=html
```

Inside container:

```bash
docker compose exec app pytest
```

## 9. Change And Update Guide

This section is the step-by-step maintenance playbook.

### 9.1 If You Modify API Request/Response Fields

Must update:

1. `app/schemas/user.py`
2. `app/routers/auth.py` response_model and endpoint logic
3. `tests/test_auth.py` payloads and assertions
4. Frontend integration doc (`FRONTEND_MAINTAINER_GUIDE.md`)
5. Any examples in `API_GUIDE.md` if still used externally

Recommended checks:

- run full tests
- open `/docs`
- validate changed endpoint through Swagger try-it-out

### 9.2 If You Add A New Endpoint

Steps:

1. Define/extend request and response schemas.
2. Implement service-layer logic first.
3. Add route in `app/routers/auth.py` with proper status and response model.
4. Add tests for happy path and at least one failure path.
5. Document endpoint behavior and error handling.

### 9.3 If You Modify User Table Columns

Mandatory sequence:

1. Update SQLAlchemy model in `app/models/user.py`.
2. Generate Alembic revision:

```bash
alembic revision --autogenerate -m "describe_change"
```

3. Review generated migration for correctness.
4. Run migration tests and app tests.
5. Update schemas and API responses if column exposed to API.
6. Update docs for new/changed fields.

### 9.4 If You Modify Token Logic Or Auth Rules

Common touchpoints:

- `app/utils/security.py` (JWT/password primitives)
- `app/services/auth_service.py` (business policy)
- `app/routers/auth.py` (public contract)
- `app/core/exceptions.py` (new error semantics)
- `tests/test_auth.py` (behavior verification)

Special caution:

- Changing `SECRET_KEY`, token structure, or token type validation can invalidate all existing tokens.
- Coordinate deployment and user session impact.

### 9.5 If You Modify Redis Key Semantics

Checklist:

1. Keep TTL and key namespace backward compatibility in mind.
2. Update helper methods in `app/database/redis.py`.
3. Update service logic in `auth_service.py`.
4. Add/adjust tests that verify lockout and blacklist behavior.
5. Communicate migration strategy if key format changed in production.

### 9.6 If You Modify Test Infrastructure

Checklist:

1. Keep `tests/conftest.py` fixture isolation guarantees.
2. Ensure DB cleanup and Redis cleanup still happen per test.
3. Validate no test order dependence.

## 10. Operational Playbooks

### 10.1 Standard Developer Workflow

1. Pull latest code.
2. Start infra (`postgres`, `redis`).
3. Run migrations.
4. Run app.
5. Run test suite.
6. Verify docs endpoints.

### 10.2 Debug Checklist For Common Issues

Issue: All protected endpoints return `401`.

- Verify `SECRET_KEY` consistency.
- Check token expiry and token type.
- Check token blacklist state in Redis.

Issue: Repeated `429` lockout.

- Inspect `login_attempts:<user_id>` in Redis.
- Wait for lockout TTL or clear specific keys in non-production debugging.

Issue: Migration mismatch.

- Verify current Alembic revision.
- Ensure app model and migration are aligned.
- Re-run migration tests.

## 11. Known Technical Debt And Improvement Suggestions

1. Session lifecycle methods exist but bearer login flow does not rely on session ids.
2. `main.py` startup currently runs `Base.metadata.create_all(...)`; in strict migration-driven environments this is often disabled in favor of Alembic-only schema control.
3. CORS is currently allow-all; production should restrict origins.
4. Add explicit API response docs (`responses={...}`) to improve Swagger error clarity.

## Feature Update (2026-04-27)

Implemented in this release:

1. PostgreSQL audit log table `audit_logs` and `AuditService`.
2. Registration email verification with Redis one-time code.
3. Forgot-password flow with Redis one-time code and direct password reset.
4. Email provider switching via env config:
- `EMAIL_PROVIDER=mailtrap`
- `EMAIL_PROVIDER=brevo`
- `EMAIL_PROVIDER=ses`
- `EMAIL_PROVIDER=mock` (tests/local)

New auth endpoints:

- `POST /api/v1/auth/verify-email/request`
- `POST /api/v1/auth/verify-email/confirm`
- `POST /api/v1/auth/forgot-password/request`
- `POST /api/v1/auth/forgot-password/reset`

## 12. Release Checklist

Before merge/deploy:

1. Tests all pass.
2. Migration scripts reviewed and reversible where applicable.
3. `/docs` and `/openapi.json` reflect expected contract.
4. Frontend guide updated if contract changed.
5. Security-sensitive env vars checked (`SECRET_KEY`, DB/Redis URLs).
6. `DEBUG` disabled for production.
