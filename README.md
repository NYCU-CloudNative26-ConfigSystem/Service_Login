# Login Service - FastAPI Microservice

高可維護性的登錄微服務，使用 FastAPI、PostgreSQL 和 Redis。

## 協作文件

- 前端 API 串接指南（English）：`FRONTEND_MAINTAINER_GUIDE.md`
- 前端 API 串接指南（繁體中文）：`FRONTEND_MAINTAINER_GUIDE.zh-TW.md`
- 後端內部開發者文件（English）：`BACKEND_INTERNAL_DEVELOPER_GUIDE.md`
- 後端內部開發者文件（繁體中文）：`BACKEND_INTERNAL_DEVELOPER_GUIDE.zh-TW.md`

## 概述

這是一個生產級別的身份驗證微服務，具有以下特性：

- **FastAPI**：現代、快速的 Python Web 框架
- **PostgreSQL**：存儲用戶身份信息（靜態數據）
- **Redis**：管理會話和登錄狀態（動態數據）
- **JWT**：安全的令牌認證
- **電子郵件驗證與忘記密碼**：使用 Redis 一次性驗證碼
- **審計日誌**：PostgreSQL `audit_logs` 記錄誰在何時做了什麼
- **高可維護性**：清晰的架構和分離關注點

## 架構設計

### 項目結構

```
cloud-naive/
├── app/
│   ├── core/              # 核心配置和異常
│   │   ├── config.py      # 應用配置
│   │   ├── exceptions.py  # 自定義異常
│   │   └── logging.py     # 日誌配置
│   ├── models/            # SQLAlchemy 數據模型
│   │   └── user.py        # 用戶模型
│   ├── schemas/           # Pydantic 驗證模型
│   │   └── user.py        # 用戶請求/響應模型
│   ├── database/          # 數據庫連接
│   │   ├── connection.py  # PostgreSQL 連接
│   │   └── redis.py       # Redis 客戶端（單例）
│   ├── services/          # 業務邏輯層
│   │   ├── user_service.py    # 用戶操作
│   │   └── auth_service.py    # 認證操作
│   ├── routers/           # API 路由
│   │   └── auth.py        # 認證端點
│   └── utils/             # 工具函數
│       └── security.py    # 密碼和 JWT 加密
├── tests/                 # 單元和集成測試
├── main.py                # FastAPI 應用入口
├── docker-compose.yml     # 容器編排
├── Dockerfile             # 應用容器配置
├── requirements.txt       # Python 依賴
└── .env.example          # 環境變量示例
```

### 數據流

#### PostgreSQL（靜態數據）

```
靜態數據存儲：
┌─────────────────────────────────────────┐
│ users 表                                  │
├──────────┬──────────┬──────────┬─────────┤
│ id       │ email    │ password │ ...     │
├──────────┼──────────┼──────────┼─────────┤
│ 1        │ user@... │ hash...  │ active  │
│ 2        │ user2@.. │ hash...  │ active  │
└──────────┴──────────┴──────────┴─────────┘
```

#### Redis（動態數據）

```
動態狀態存儲：
session:{session_id} → user_id               # 用戶會話（TTL: 24h）
login_attempts:{user_id} → count             # 登錄嘗試計數（TTL: 15m）
cache:{key} → value                          # 通用緩存
email_code:register:{email} → 6-digit code   # 註冊驗證碼（TTL 可配置）
email_code:password_reset:{email} → code     # 忘記密碼驗證碼（TTL 可配置）
```

#### PostgreSQL（審計日誌）

`audit_logs` 會記錄安全敏感操作，例如：

- REGISTER
- EMAIL_VERIFIED
- LOGIN_SUCCESS / LOGIN_FAILED
- PASSWORD_RESET_CODE_SENT / PASSWORD_RESET_SUCCESS
- LOGOUT / TOKEN_REFRESH

## 快速開始

### 前置要求

- Docker 和 Docker Compose
- 或者本地 Python 3.11+、PostgreSQL、Redis

### 使用 Docker Compose（推薦）

1. **複製環境配置**

```bash
cp .env.example .env
```

2. **啟動服務**

```bash
docker-compose up -d
```

預設會綁定到主機 `18000` 埠（避免和你本機既有的 `8000` 服務衝突）。
如需調整，編輯 `.env` 中的 `APP_HOST_PORT`。

3. **訪問應用**

- API 文檔：http://localhost:18000/docs
- 健康檢查：http://localhost:18000/health

4. **如果你正在使用 ngrok**

```bash
ngrok http 18000
```

如果你要保留原本 `localhost:8000` 給其他程式，可維持目前設定不變。

如果你只想啟動資料庫（不啟動 API 容器，完全不占用 API 埠）：

```bash
docker-compose up -d postgres redis
```

### 本地開發

1. **創建虛擬環境**

```bash
python -m venv venv
# Linux / macOS
source venv/bin/activate

# Windows PowerShell
venv\Scripts\Activate.ps1
```

2. **安裝依賴**

```bash
pip install -r requirements.txt
```

3. **配置環境變量**

```bash
cp .env.example .env
# 編輯 .env 文件，配置本地數據庫和 Redis 地址
```

4. **啟動 PostgreSQL 和 Redis**

```bash
# 建議使用 Compose 啟動（避免重複建立容器造成埠衝突）
docker compose up -d postgres redis
```

5. **運行應用**

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 18000
```

若要透過環境變量設定埠號：

```bash
# Linux / macOS
export APP_PORT=18000
uvicorn main:app --reload --host 0.0.0.0 --port $APP_PORT
```

```powershell
# Windows PowerShell
$env:APP_PORT = "18000"
uvicorn main:app --reload --host 0.0.0.0 --port $env:APP_PORT
```

## API 端點

## 資料庫遷移

這個專案已經接上 Alembic。當你修改 `app/models/` 裡的 ORM model 時，請用 migration 管理 schema 變更，不要只依賴啟動時的自動建表。

常用指令：

```bash
make migrate
make migrate-down
make migrate-new message="add new column"
```

如果你在容器外直接執行，也可以用：

```bash
alembic upgrade head
alembic downgrade -1
alembic revision --autogenerate -m "add new column"
```

### 認證相關

#### 註冊用戶

```
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "username",
  "password": "securepassword123",
  "full_name": "Full Name"
}

Response (201):
{
  "id": 1,
  "email": "user@example.com",
  "username": "username",
  "full_name": "Full Name",
  "is_active": true,
  "is_verified": false,
  "created_at": "2024-03-28T...",
  "updated_at": "2024-03-28T...",
  "last_login_at": null
}
```

註冊成功後系統會自動寄出 email 驗證碼，使用者需要完成驗證後才能登入。

#### 請求註冊驗證碼（重寄）

```
POST /api/v1/auth/verify-email/request
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### 確認電子郵件驗證

```
POST /api/v1/auth/verify-email/confirm
Content-Type: application/json

{
  "email": "user@example.com",
  "code": "123456"
}

Response (200):
{
  "message": "Email verified successfully"
}
```

#### 登錄

```
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}

Response (200):
{
  "access_token": "eyJ0eXAiOiJKV1QiLC...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLC...",
  "token_type": "bearer",
  "user": { ... }
}
```

若尚未完成 email 驗證，會回傳 `403 Email is not verified`。

#### 獲取當前用戶

```
GET /api/v1/auth/me
Authorization: Bearer {access_token}

Response (200):
{
  "id": 1,
  "email": "user@example.com",
  ...
}
```

#### 刷新令牌

```
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLC..."
}

Response (200):
{
  "access_token": "eyJ0eXAiOiJKV1QiLC...",
  "token_type": "bearer"
}
```

#### 登出

```
POST /api/v1/auth/logout
Authorization: Bearer {access_token}

Response (200):
{
  "message": "Logged out successfully"
}
```

#### 忘記密碼：請求驗證碼

```
POST /api/v1/auth/forgot-password/request
Content-Type: application/json

{
  "email": "user@example.com"
}

Response (200):
{
  "message": "If the email exists, a reset code has been sent"
}
```

#### 忘記密碼：使用驗證碼重設

```
POST /api/v1/auth/forgot-password/reset
Content-Type: application/json

{
  "email": "user@example.com",
  "code": "654321",
  "new_password": "newsecurepassword123"
}

Response (200):
{
  "message": "Password reset successfully"
}
```

## 安全特性

### 密碼保護

- 使用 bcrypt 的 12 輪加鹽哈希
- 密碼不存儲為純文本

### JWT 令牌

- 有效期：30 分鐘（訪問令牌）、7 天（刷新令牌）
- 簽名使用 HS256 算法
- 包含 `sub`（用戶ID）、`iat`（簽發時間）、`exp`（過期時間）

### 登錄嘗試限制

- 5 次失敗登錄嘗試後鎖定賬戶
- 鎖定時間：15 分鐘
- 成功登錄後重置計數

### 會話管理

- Redis 中存儲活躍會話
- 24 小時自動過期
- 服務器端會話驗證

## 配置管理

所有配置通過環境變量管理，存儲在 `.env` 文件中：

```env
# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/auth_service

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email 驗證碼 TTL（秒）
EMAIL_VERIFICATION_CODE_TTL_SECONDS=600
PASSWORD_RESET_CODE_TTL_SECONDS=600

# Email provider: mock | mailtrap | brevo | ses
EMAIL_PROVIDER=mock
EMAIL_FROM=no-reply@example.com

# Mailtrap (official API client)
MAILTRAP_API_TOKEN=
MAILTRAP_SENDER_NAME=Mailtrap Test
MAILTRAP_CATEGORY=Authentication

# Brevo
BREVO_API_KEY=

# Amazon SES
SES_REGION=us-east-1
SES_ACCESS_KEY_ID=
SES_SECRET_ACCESS_KEY=

# 應用
APP_NAME=Login Service
DEBUG=False
LOG_LEVEL=INFO

# 安全設置
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_SECONDS=900
SESSION_EXPIRE_SECONDS=86400
```

## 錯誤處理

應用使用統一的異常處理機制：

- **401 Unauthorized**：無效或過期的認證信息
- **400 Bad Request**：用戶已存在等驗證失敗
- **400 Bad Request**：驗證碼錯誤/過期、用戶已存在等
- **404 Not Found**：用戶不存在
- **403 Forbidden**：尚未完成 email 驗證
- **429 Too Many Requests**：賬戶由於登錄嘗試過多被鎖定

## 日誌記錄

所有重要操作都被記錄：

- 用戶註冊、登錄、登出
- 認證失敗
- 賬戶鎖定
- 數據庫操作
- 系統啟動/關閉

日誌級別由環境變量 `LOG_LEVEL` 控制。

## 測試

### 運行所有測試

```bash
pytest
```

### 運行特定測試

```bash
pytest tests/test_auth.py::TestAuthEndpoints::test_email_verification_then_login_success -v
```

### 生成覆蓋率報告

```bash
pytest --cov=app tests/
```

## 可維護性特性

### 1. 清晰的分層架構

- **Models**：數據結構
- **Schemas**：請求/響應驗證
- **Services**：業務邏輯
- **Routers**：API 端點
- **Utils**：可重用工具

### 2. 依賴注入

- FastAPI 的 Depends 用於自動注入依賴
- 使於測試和模組替換

### 3. 類型提示

- 完整的 Python 類型提示
- 提升代碼可讀性和IDE支持

### 4. 異常處理

- 統一的自定義異常
- 清晰的錯誤消息

### 5. 日誌記錄

- 結構化日誌
- 便於調試和監控

### 6. 測試

- 單元測試覆蓋
- 固定和模擬支持

## 生產部署建議

1. **安全性**

   - 更改 `SECRET_KEY` 為強隨機值
   - 設置 `DEBUG=False`
   - 配置 CORS 以接受特定的域名
2. **性能**

   - 配置適當的 `pool_size` 和 `max_overflow`
   - 實施速率限制
   - 考慮使用 Nginx 作為反向代理
3. **監控**

   - 集成日誌聚合（如 ELK Stack）
   - 設置性能監控（如 Prometheus）
   - 配置錯誤追蹤（如 Sentry）
4. **數據庫**

   - 定期備份
   - 配置複製以實現高可用性
   - 使用連接池
5. **Redis**

   - 配置持久化（RDB 或 AOF）
   - 實施紅隊（哨兵）模式以實現高可用性
   - 監控記憶體使用情況

## 擴展功能

### 可輕鬆添加的功能：

1. 雙因素認證 (2FA)
2. OAuth 2.0 集成
3. 用戶角色和權限
4. IP 白名單
5. 設備管理
