# 前端與維護人員協作文件

本文件提供給前端工程師、後端維護者與 DevOps 維運人員，作為此服務的單一交接入口。

## 1. 服務定位

- 服務名稱：Login Service
- 主要責任：註冊、登入、JWT 驗證、Token 刷新、登出黑名單
- 後端框架：FastAPI
- 資料儲存：
  - PostgreSQL：使用者靜態資料
  - Redis：登入失敗計數、Token 黑名單、暫存資料

## 2. 啟動方式與連線資訊

### 2.1 使用 Docker Compose（建議）

```bash
docker compose up -d
```

預設對外 API 位址：

- `http://localhost:18000`

預設文件與健康檢查：

- Swagger：`http://localhost:18000/docs`
- Health：`http://localhost:18000/health`

### 2.2 只啟動基礎設施（本機跑 API）

```bash
docker compose up -d postgres redis
uvicorn main:app --reload --host 0.0.0.0 --port 18000
```

## 3. 前端整合規範

### 3.1 API Base URL

本機開發建議：

- `http://localhost:18000/api/v1`

認證路由前綴：

- `/auth`

完整範例：

- 註冊：`POST http://localhost:18000/api/v1/auth/register`

### 3.2 Auth API 一覽

#### 註冊

- Method/Path：`POST /api/v1/auth/register`
- Request JSON：

```json
{
  "email": "john@example.com",
  "username": "john_doe",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

- 成功回應：`201 Created`
- 重要欄位限制：
  - `email`：合法 email
  - `username`：3-100 字元
  - `password`：至少 8 字元

#### 登入

- Method/Path：`POST /api/v1/auth/login`
- Request JSON：

```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```

- 成功回應：`200 OK`
- Response JSON：

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "john@example.com",
    "username": "john_doe",
    "full_name": "John Doe",
    "is_active": true,
    "is_verified": false,
    "created_at": "2026-03-29T00:00:00",
    "updated_at": "2026-03-29T00:00:00",
    "last_login_at": "2026-03-29T00:00:00"
  }
}
```

#### 取得當前使用者

- Method/Path：`GET /api/v1/auth/me`
- Header：`Authorization: Bearer <access_token>`
- 成功回應：`200 OK`
- 未帶 Token：`403 Forbidden`（來自 HTTPBearer）
- Token 無效或過期：`401 Unauthorized`

#### 刷新 Access Token

- Method/Path：`POST /api/v1/auth/refresh`
- Request JSON：

```json
{
  "refresh_token": "..."
}
```

- 成功回應：`200 OK`
- Response JSON：

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

#### 登出

- Method/Path：`POST /api/v1/auth/logout`
- Header：`Authorization: Bearer <access_token>`
- Request JSON：

```json
{
  "refresh_token": "..."
}
```

- 成功回應：`200 OK`
- Response JSON：

```json
{
  "message": "Logged out successfully"
}
```

### 3.3 前端 Token 管理建議

- `access_token`：用於一般 API 請求，過期時間較短（預設 30 分鐘）
- `refresh_token`：只用於換新 `access_token`（預設 7 天）
- 每次 API 請求附帶 `Authorization: Bearer <access_token>`
- 收到 `401` 且確認為 access token 過期時，呼叫 `/auth/refresh` 取得新 token 後重送原請求
- 刷新失敗或 refresh token 失效時，清空本地登入狀態並導回登入頁
- 登出時務必帶上目前 `access_token` 與 `refresh_token`

### 3.4 常見錯誤碼對照

- `400 Bad Request`：註冊資料衝突（email 或 username 已存在）
- `401 Unauthorized`：帳密錯誤、Token 無效、Token 過期、Token 黑名單
- `403 Forbidden`：未帶 Authorization header 存取保護端點
- `404 Not Found`：使用者不存在（特定流程）
- `422 Unprocessable Entity`：請求 JSON 格式錯或欄位驗證失敗
- `429 Too Many Requests`：連續登入失敗達上限，帳號暫時鎖定
- `500 Internal Server Error`：未處理例外

## 4. 維護人員操作手冊

### 4.1 常用命令

```bash
# 啟動全部服務
docker compose up -d

# 僅啟動資料庫與 Redis
docker compose up -d postgres redis

# 關閉並移除容器
docker compose down

# 關閉並清除 volume（重置資料）
docker compose down -v

# 看 app 日誌
docker compose logs -f app

# 執行測試
pytest tests/ -v

# coverage
pytest tests/ --cov=app --cov-report=html --cov-report=term
```

### 4.2 環境變數重點

- `DATABASE_URL`：PostgreSQL 連線字串
- `REDIS_URL`：Redis 連線字串
- `SECRET_KEY`：JWT 簽章密鑰，正式環境必須更換
- `ACCESS_TOKEN_EXPIRE_MINUTES`：Access Token 有效時間
- `REFRESH_TOKEN_EXPIRE_DAYS`：Refresh Token 有效天數
- `MAX_LOGIN_ATTEMPTS`：錯誤登入嘗試上限（預設 5）
- `LOCKOUT_DURATION_SECONDS`：帳號鎖定秒數（預設 900）
- `APP_HOST_PORT`：主機對外埠（預設 18000）

### 4.3 部署前檢查清單

- `SECRET_KEY` 是否已替換為高強度值
- CORS 是否限制為實際前端網域（目前程式為全開）
- `DEBUG` 是否關閉
- `LOG_LEVEL` 是否符合環境需求
- `DATABASE_URL`、`REDIS_URL` 是否使用正式環境服務
- Swagger (`/docs`) 是否依需求開放或限制

### 4.4 故障排查速查

#### 問題：前端全部回 401

- 檢查前端是否使用過期 `access_token`
- 檢查 `SECRET_KEY` 是否有變更（變更後舊 token 全失效）
- 檢查 refresh token 是否已進入黑名單或過期

#### 問題：登入回 429

- 使用者達到錯誤登入上限
- 等待 `LOCKOUT_DURATION_SECONDS` 後再試
- 可進 Redis 查 `login_attempts:<user_id>`

#### 問題：服務起不來

- 確認 `.env` 必填值都存在
- 檢查 postgres/redis healthcheck 狀態
- 查看容器日誌：`docker compose logs -f app postgres redis`

## 5. API 合約變更流程（建議）

- 先更新 schema 與 router
- 同步更新本文件與 `API_GUIDE.md`
- 補對應測試（至少 happy path + 1 個 failure path）
- 通知前端本次變更內容（欄位、錯誤碼、token 流程）

## 6. 前端協作建議（避免踩雷）

- 不要把 `refresh_token` 放在 URL query
- 遇到 `401` 不要無限 refresh 重試，需有限次數與保護機制
- `logout` 成功與否都應清空本地登入狀態
- 優先依賴後端回傳 `detail` 顯示錯誤訊息

## 7. 聯絡與交接備註

- 若新增認證機制（OAuth、MFA、email verify），請先擴充本文件第 3 章與第 5 章
- 若新增端點，請維持 `/api/v1` 版本前綴，避免破壞前端相容性
