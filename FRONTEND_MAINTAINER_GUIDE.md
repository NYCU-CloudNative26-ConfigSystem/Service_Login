# Frontend API Integration Guide

This document is for frontend engineers integrating with this authentication service.

## 1. Service Scope

This service provides:

- User registration
- Registration email verification
- User login
- Token-based authentication with JWT
- Access token refresh
- Forgot-password reset via email verification code
- Logout with token blacklist
- Current-user lookup

Base URL in local development:

- `http://localhost:18000`

API prefix:

- `http://localhost:18000/api/v1`

Swagger docs:

- `http://localhost:18000/docs`

OpenAPI JSON:

- `http://localhost:18000/openapi.json`

## 2. Startup Checklist For Frontend

1. Confirm backend is running.
2. Open `http://localhost:18000/health` and verify status is healthy.
3. Open `http://localhost:18000/docs` and verify auth endpoints are listed.
4. Set frontend env var (example):

```bash
VITE_API_BASE_URL=http://localhost:18000/api/v1
```

## 3. Authentication API Contract

All auth endpoints are under `/api/v1/auth`.

### 3.1 Register

- Method: `POST`
- Path: `/api/v1/auth/register`
- Auth required: No

Request body:

```json
{
  "email": "john@example.com",
  "username": "john_doe",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

Validation notes:

- `email`: valid email format
- `username`: 3 to 100 chars
- `password`: at least 8 chars
- `full_name`: optional, max 255 chars
- Password hashing follows bcrypt byte-length limit; very long UTF-8 passwords may be rejected with 400.

Success response:

- Status: `201 Created`

Example response:

```json
{
  "id": 1,
  "email": "john@example.com",
  "username": "john_doe",
  "full_name": "John Doe",
  "is_active": true,
  "is_verified": false,
  "created_at": "2026-04-26T12:00:00",
  "updated_at": "2026-04-26T12:00:00",
  "last_login_at": null
}
```

Common failures:

- `400`: duplicate email or username
- `422`: invalid schema or missing required fields

Behavior note:

- Registration triggers an email verification code. User cannot login before verification.

### 3.1.1 Request/Resend Email Verification Code

- Method: `POST`
- Path: `/api/v1/auth/verify-email/request`
- Auth required: No

Request body:

```json
{
  "email": "john@example.com"
}
```

### 3.1.2 Confirm Email Verification Code

- Method: `POST`
- Path: `/api/v1/auth/verify-email/confirm`
- Auth required: No

Request body:

```json
{
  "email": "john@example.com",
  "code": "123456"
}
```

Success response:

```json
{
  "message": "Email verified successfully"
}
```

### 3.2 Login

- Method: `POST`
- Path: `/api/v1/auth/login`
- Auth required: No

Request body:

```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```

Success response:

- Status: `200 OK`

Example response:

```json
{
  "access_token": "<jwt_access_token>",
  "refresh_token": "<jwt_refresh_token>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "john@example.com",
    "username": "john_doe",
    "full_name": "John Doe",
    "is_active": true,
    "is_verified": false,
    "created_at": "2026-04-26T12:00:00",
    "updated_at": "2026-04-26T12:00:00",
    "last_login_at": "2026-04-26T12:05:00"
  }
}
```

Common failures:

- `401`: invalid email/password, invalid token in downstream flow
- `403`: email is not verified yet
- `429`: account temporarily locked after max failed attempts
- `422`: invalid request payload

### 3.3 Get Current User

- Method: `GET`
- Path: `/api/v1/auth/me`
- Auth required: Yes (`Authorization: Bearer <access_token>`)

Success response:

- Status: `200 OK`
- Body: same shape as user object in login response

Common failures:

- `403`: missing bearer token header (FastAPI `HTTPBearer` behavior)
- `401`: invalid/expired token or blacklisted token

### 3.4 Refresh Access Token

- Method: `POST`
- Path: `/api/v1/auth/refresh`
- Auth required: No (refresh token is in body)

Request body:

```json
{
  "refresh_token": "<jwt_refresh_token>"
}
```

Success response:

- Status: `200 OK`

```json
{
  "access_token": "<new_access_token>",
  "token_type": "bearer"
}
```

Common failures:

- `401`: refresh token expired, invalid, wrong token type, or blacklisted
- `422`: invalid payload

### 3.5 Logout

- Method: `POST`
- Path: `/api/v1/auth/logout`
- Auth required: Yes (`Authorization: Bearer <access_token>`)

Request body:

```json
{
  "refresh_token": "<jwt_refresh_token>"
}
```

Success response:

- Status: `200 OK`

```json
{
  "message": "Logged out successfully"
}
```

Behavior notes:

- Both current access token and submitted refresh token are added to Redis blacklist with TTL.
- Once blacklisted, tokens should be considered immediately invalid.

### 3.6 Forgot Password - Request Code

- Method: `POST`
- Path: `/api/v1/auth/forgot-password/request`
- Auth required: No

Request body:

```json
{
  "email": "john@example.com"
}
```

Success response:

```json
{
  "message": "If the email exists, a reset code has been sent"
}
```

### 3.7 Forgot Password - Reset Password

- Method: `POST`
- Path: `/api/v1/auth/forgot-password/reset`
- Auth required: No

Request body:

```json
{
  "email": "john@example.com",
  "code": "654321",
  "new_password": "NewSecurePass123!"
}
```

Success response:

```json
{
  "message": "Password reset successfully"
}
```

## 4. Full Frontend Auth Flow

### 4.1 First Login Flow

1. User submits credentials.
2. Frontend calls `POST /auth/register` if new user.
3. Frontend asks user to enter email verification code.
4. Frontend calls `POST /auth/verify-email/confirm`.
5. Frontend calls `POST /auth/login`.
6. Frontend stores `access_token` and `refresh_token`.
7. Frontend calls `GET /auth/me` to hydrate current user state if needed.
8. Frontend routes user to authenticated pages.

### 4.5 Forgot Password Flow

1. User provides account email.
2. Frontend calls `POST /auth/forgot-password/request`.
3. User inputs code from email and a new password.
4. Frontend calls `POST /auth/forgot-password/reset`.
5. Frontend routes user back to login and prompts login with new password.

### 4.2 Authenticated API Request Flow

1. Read `access_token`.
2. Add header `Authorization: Bearer <access_token>`.
3. If API returns 200, continue.
4. If API returns 401, run refresh flow once.

### 4.3 Refresh Flow

1. Call `POST /auth/refresh` with `refresh_token`.
2. If success, replace `access_token` and retry original request once.
3. If refresh fails, clear local auth state and redirect to login.

### 4.4 Logout Flow

1. Call `POST /auth/logout` with both:
- Header bearer access token
- Body refresh token
2. Regardless of API result, clear local tokens and user state.
3. Redirect to login page.

## 5. Recommended Frontend Token Storage Strategy

Preferred:

- Access token: memory store (or short-lived storage)
- Refresh token: secure HTTP-only cookie if architecture supports it

If using local storage/session storage, ensure:

- strict XSS protection
- token lifecycle handling
- clear on logout and refresh failure

## 6. Error Handling Matrix

| HTTP | Typical Meaning | Frontend Action |
|---|---|---|
| 400 | Business rule violation (for example duplicate user, password byte limit) | Show validation/business error |
| 401 | Token invalid/expired or credentials invalid | Attempt refresh once; if still 401, force relogin |
| 403 | Missing auth header or email not verified | Check interceptor or route to verify-email flow |
| 404 | Resource/user not found | Show not found state |
| 422 | Payload validation failed | Map backend validation to form fields |
| 429 | Account locked due to repeated failures | Show lockout message and retry later |
| 500 | Server-side unexpected exception | Show generic error and capture diagnostics |

## 7. Practical Request Examples

### cURL Login

```bash
curl -X POST "http://localhost:18000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123!"
  }'
```

### cURL Current User

```bash
curl -X GET "http://localhost:18000/api/v1/auth/me" \
  -H "Authorization: Bearer <access_token>"
```

### cURL Refresh

```bash
curl -X POST "http://localhost:18000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<refresh_token>"
  }'
```

## 8. Frontend Change Impact Guide

When backend changes happen, verify these first:

1. Endpoint path or method changed
2. Required request fields changed
3. Response schema changed (including nested `user` fields)
4. Error codes changed
5. Token TTL changed

If any of the above changed, frontend must update:

- API client typings/interfaces
- form validation rules
- auth interceptor/refresh logic
- user state normalization logic

## 9. QA Scenarios Frontend Should Always Run

1. Register success + duplicate email failure
2. Login blocked before email verification (`403`)
3. Email verification confirm success then login success
4. Forgot-password request + reset + login with new password
5. Access protected endpoint without token (`403`)
6. Access protected endpoint with expired token (`401` then refresh)
7. Refresh with invalid token (`401`, force logout)
8. Logout then re-use old token (`401`)
9. Lockout after repeated failed login (`429`)
