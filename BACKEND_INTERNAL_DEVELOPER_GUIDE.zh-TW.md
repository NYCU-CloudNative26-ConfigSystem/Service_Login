# 後端內部開發者文件（繁體中文）

本文件提供後端維護與擴充時使用，涵蓋專案架構、資料庫設計、API 邏輯、測試策略與變更流程。

## 1. 專案全景與環境設定

### 1.1 技術棧

- Runtime：Python 3.11（容器基準）
- Web Framework：FastAPI
- ORM：SQLAlchemy 2.x
- Migration：Alembic
- Database：PostgreSQL
- Cache/State：Redis
- Auth：JWT（access + refresh）
- Test：Pytest + FastAPI TestClient

### 1.2 專案目錄結構

```text
app/
  core/
    config.py          # 環境變數設定
    exceptions.py      # 自訂 HTTP 例外
    logging.py         # 日誌設定
  database/
    connection.py      # SQLAlchemy engine/session/base
    redis.py           # Redis 單例客戶端與操作封裝
  models/
    user.py            # 使用者資料表模型
    audit_log.py       # 審計日誌資料表模型
  schemas/
    user.py            # Pydantic request/response DTO
  services/
    user_service.py    # 使用者業務邏輯
    auth_service.py    # token/session/登入失敗計數邏輯
    audit_service.py   # 審計日誌寫入服務
    email_service.py   # 可切換 email provider
  routers/
    auth.py            # HTTP 端點
main.py                # FastAPI 啟動入口、middleware、event
migrations/
  env.py               # Alembic 執行環境整合
  versions/
    0001_initial_users_table.py
tests/
  conftest.py
  test_auth.py
  test_migration.py
```

### 1.3 本機開發環境建立

1. 使用 Python 3.11 或 3.12 建立虛擬環境。
2. 安裝相依套件。
3. 複製 `.env.example` 為 `.env`。
4. 啟動 PostgreSQL 與 Redis。
5. 啟動 API。

指令範例：

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env

docker compose up -d postgres redis
uvicorn main:app --reload --host 0.0.0.0 --port 18000
```

啟動整套容器：

```bash
docker compose up -d
```

### 1.4 重要環境變數

必要：

- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`

重要可調整設定：

- `ALGORITHM`（預設 `HS256`）
- `ACCESS_TOKEN_EXPIRE_MINUTES`（預設 30）
- `REFRESH_TOKEN_EXPIRE_DAYS`（預設 7）
- `MAX_LOGIN_ATTEMPTS`（預設 5）
- `LOCKOUT_DURATION_SECONDS`（預設 900）
- `SESSION_EXPIRE_SECONDS`（預設 86400）
- `MAX_PASSWORD_LENGTH`（預設 72，對應 bcrypt byte limit）

## 2. 執行架構與請求流程

### 2.1 請求路徑

1. 請求進入 `main.py` FastAPI 應用。
2. Middleware 記錄 method/path/status/latency。
3. Router 導向 `app/routers/auth.py` 對應端點。
4. 端點呼叫 `UserService` 或 `AuthService`。
5. Service 存取 PostgreSQL/Redis。
6. 使用 Pydantic response model 輸出。

### 2.2 分層職責

Router 層：

- API 合約與 HTTP 行為
- 依賴注入（DB、token）
- 回應模型綁定

Service 層：

- 商業規則
- 多步驟流程控制
- Side effects（登入計數、黑名單）

Database/Cache 層：

- SQLAlchemy session 管理
- Redis key 設計與 TTL 操作

Schema/Model 層：

- Request/Response 驗證
- 資料表結構定義

## 3. 資料庫架構（Database Schema）

目前核心業務表為 `users`。

### 3.1 users 表

| 欄位 | 型別 | 可空值 | 說明 |
|---|---|---|---|
| id | Integer | 否 | 主鍵、索引 |
| email | String(255) | 否 | 唯一、索引 |
| username | String(100) | 否 | 唯一、索引 |
| hashed_password | String(255) | 否 | bcrypt 雜湊密碼 |
| full_name | String(255) | 是 | 使用者顯示名稱 |
| is_active | Boolean | 是（預設 true） | 帳號啟用狀態 |
| is_verified | Boolean | 是（預設 false） | 驗證保留欄位 |
| created_at | DateTime | 否 | 建立時間 |
| updated_at | DateTime | 否 | 更新時間（onupdate） |
| last_login_at | DateTime | 是 | 上次成功登入時間 |

Migration 建立索引：

- `ix_users_id`
- `ix_users_email`（unique）
- `ix_users_username`（unique）
- `ix_users_is_active`

### 3.2 Migration 基線

- 初始版號：`0001_initial_users_table`
- Alembic 在 `migrations/env.py` 透過 `Base.metadata` 比對模型

常用指令：

```bash
alembic upgrade head
alembic downgrade -1
```

## 4. Redis 資料模型

目前使用到的 key：

- `session:<session_id>` -> `<user_id>`（TTL = `SESSION_EXPIRE_SECONDS`）
- `login_attempts:<user_id>` -> 失敗次數（TTL = `LOCKOUT_DURATION_SECONDS`）
- `blacklist:<token>` -> `true`（TTL 依 token 壽命）
- `cache:<key>` -> JSON 字串（泛用快取）
- `email_code:register:<email>` -> 註冊驗證碼（TTL = `EMAIL_VERIFICATION_CODE_TTL_SECONDS`）
- `email_code:password_reset:<email>` -> 忘記密碼驗證碼（TTL = `PASSWORD_RESET_CODE_TTL_SECONDS`）

維運影響：

- 鎖定機制完全由 Redis 計數與 TTL 控制
- 登出失效主要由 token 黑名單控制
- `flushdb` 會清空鎖定狀態與黑名單

## 5. API 設計規範與邏輯

API 前綴：`/api/v1/auth`

### 5.1 註冊：`POST /register`

流程：

- 驗證 request schema
- 檢查 email/username 是否重複
- bcrypt 雜湊密碼
- 建立使用者資料
- 回傳 `UserResponse`

### 5.2 登入：`POST /login`

流程：

- 依 email 查使用者
- 檢查 Redis 鎖定計數
- 驗證密碼與 `is_active`
- 驗證 `is_verified`，未驗證會回傳 `403`
- 成功時清除登入失敗計數
- 更新 `last_login_at`
- 產生 access/refresh token 並回傳

失敗流程：

- 密碼錯誤會遞增 `login_attempts:<user_id>`
- 達上限觸發 `429 AccountLockedException`

### 5.3 取得當前使用者：`GET /me`

流程：

- 需 Bearer access token
- 檢查 JWT 簽章、過期、token type
- 檢查 token 黑名單
- 依 `sub` 查詢使用者

### 5.4 刷新 token：`POST /refresh`

流程：

- body 帶 refresh token
- 先檢查是否黑名單
- 驗證 token type 必須為 `refresh`
- 核發新的 access token

### 5.5 登出：`POST /logout`

流程：

- Header 需帶 access token
- Body 需帶 refresh token
- 將兩者都加入黑名單

實作注意：

- 目前登入主流程並未建立 session 作為 bearer 驗證依據
- 因此目前主要失效機制是 token 黑名單

### 5.6 例外與錯誤碼規範

`app/core/exceptions.py`：

- `401 InvalidCredentialsException`
- `401 InvalidTokenException`
- `401 TokenBlacklistedException`
- `404 UserNotFoundException`
- `400 UserAlreadyExistsException`
- `400 PasswordTooLongException`
- `429 AccountLockedException`
- `403`（HTTPBearer 未帶 token）

未捕捉例外會由 `main.py` 全域 handler 轉成 `500 Internal server error`。

## 6. 安全設計

### 6.1 密碼

- bcrypt rounds=12
- 檢查 UTF-8 byte 長度（預設上限 72）
- 超出時丟 `PasswordTooLongException`

### 6.2 JWT payload

Access token：

- `sub`：user id
- `iat`：issued at
- `exp`：expire time
- `type`：`access`

Refresh token：

- 欄位同上，`type`：`refresh`

### 6.3 Token 驗證

`decode_token` 會驗證：

- 簽章
- 過期時間
- 演算法
- token type 是否符合預期

## 7. API 文件產生方式與維護

本專案 `/docs` 與 `/openapi.json` 為 FastAPI 自動生成。

產生來源：

- `main.py`：`title` / `version` / `description`
- `app/routers/auth.py`：路徑、tags、response_model
- `app/schemas/user.py`：request/response schema

若要讓文件更完整，建議：

1. 在 route decorator 增加 `summary` 與 `description`
2. 補齊每個端點的 `response_model`
3. 在 Pydantic `Field(...)` 加上 description/examples
4. 在 route decorator 用 `responses={...}` 明確列錯誤回應

## 8. 測試策略與指令

### 8.1 目前測試覆蓋

`tests/test_auth.py`：

- 註冊成功/失敗
- 登入成功/失敗
- 鎖定機制
- 取得當前使用者
- 刷新 token
- 密碼長度限制
- token encode/decode

`tests/test_migration.py`：

- Alembic upgrade/downgrade
- users 表建立與移除
- alembic version 驗證

### 8.2 測試執行模型

- SQL 測試使用 SQLite 臨時資料庫 `test.db`
- 每個測試前後會 flush Redis
- 透過 dependency override 注入測試 DB session

### 8.3 常用指令

```bash
pytest tests/ -v
pytest tests/test_auth.py -v
pytest tests/test_migration.py -v
pytest tests/ --cov=app --cov-report=term --cov-report=html
```

容器內：

```bash
docker compose exec app pytest
```

## 9. 修改與更新指南

以下是實際維護時的變更清單。

### 9.1 修改 API request/response 欄位

必須同步調整：

1. `app/schemas/user.py`
2. `app/routers/auth.py` 的 response_model 與端點邏輯
3. `tests/test_auth.py` 的 payload 與 assertion
4. 前端文件（`FRONTEND_MAINTAINER_GUIDE.md` 與 zh-TW 版）
5. 外部 API 範例文件（若使用 `API_GUIDE.md`）

建議驗證：

- 跑完整測試
- 打開 `/docs` 確認合約
- 用 Swagger Try it out 手動驗證

### 9.2 新增 API 端點

步驟：

1. 先定義 schema
2. 再實作 service business logic
3. 在 router 新增 route（method/status/response_model）
4. 撰寫 happy path + failure path 測試
5. 更新 API 文件與前端串接文件

### 9.3 修改資料表欄位

必做順序：

1. 更新 `app/models/user.py`
2. 產生 migration：

```bash
alembic revision --autogenerate -m "describe_change"
```

3. 檢查 migration 內容（型別、nullable、index、default）
4. 跑 migration 測試與 API 測試
5. 若欄位有對外暴露，更新 schema 與 response
6. 更新前後端文件

### 9.4 修改 Token/Auth 規則

常見連動檔案：

- `app/utils/security.py`
- `app/services/auth_service.py`
- `app/routers/auth.py`
- `app/core/exceptions.py`
- `tests/test_auth.py`

注意事項：

- 變更 `SECRET_KEY` 或 token payload/type 規則，會使舊 token 全數失效
- 上線前需先規劃使用者會話影響

### 9.5 修改 Redis key 設計

檢查清單：

1. 評估是否向後相容（key 命名、TTL）
2. 更新 `app/database/redis.py`
3. 更新 `auth_service.py` 使用邏輯
4. 補測試驗證鎖定與黑名單
5. 生產環境若改 key 格式，需有過渡策略

### 9.6 修改測試基礎設施

檢查清單：

1. 確保 `tests/conftest.py` 隔離性不被破壞
2. 確保每次測試 DB/Redis 都可清理
3. 確保測試無順序依賴

## 10. 維運操作手冊

### 10.1 日常開發流程

1. 更新程式碼
2. 啟動 `postgres` 與 `redis`
3. 執行 migration
4. 啟動 API
5. 跑測試
6. 檢查 `/docs` 與 `/openapi.json`

### 10.2 常見問題排查

問題：保護端點全部 `401`

- 檢查 `SECRET_KEY` 是否一致
- 檢查 token 是否過期與 type 是否正確
- 檢查 Redis 黑名單狀態

問題：持續出現 `429`

- 檢查 `login_attempts:<user_id>` 計數
- 等待鎖定 TTL 或在非正式環境清理 key

問題：migration 不一致

- 檢查 Alembic 當前版本
- 確認 model 與 migration 同步
- 重跑 migration 測試

## 11. 已知技術債與改善建議

1. 目前 session 方法存在，但登入驗證主流程未使用 session id
2. `main.py` 啟動時會 `Base.metadata.create_all(...)`，若採嚴格 migration 管理可考慮改為 Alembic 單一路徑
3. CORS 現為 allow-all，正式環境應限制白名單
4. 建議在 route 補 `responses={...}` 提升 Swagger 錯誤文件可讀性

## 功能更新（2026-04-27）

本次版本已實作：

1. PostgreSQL 審計日誌 `audit_logs` 與 `AuditService`
2. 註冊 email 驗證（Redis 驗證碼）
3. 忘記密碼驗證與直接重設（Redis 驗證碼）
4. Email provider 可切換（Mailtrap/Brevo/Amazon SES）

新增 API：

- `POST /api/v1/auth/verify-email/request`
- `POST /api/v1/auth/verify-email/confirm`
- `POST /api/v1/auth/forgot-password/request`
- `POST /api/v1/auth/forgot-password/reset`

## 12. 發版前檢查清單

1. 所有測試通過
2. migration 已審查且可回滾
3. `/docs` 與 `/openapi.json` 合約符合預期
4. 前端文件同步更新（若 API 有變更）
5. 安全環境變數已確認（`SECRET_KEY`、DB、Redis）
6. 生產環境 `DEBUG` 已關閉
