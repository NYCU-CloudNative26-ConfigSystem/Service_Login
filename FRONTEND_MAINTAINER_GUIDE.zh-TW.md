# 前端 API 串接指南（繁體中文）

本文件提供前端工程師串接此認證服務時使用，內容包含 API 合約、登入流程、Token 更新策略與錯誤處理建議。

## 1. 服務範圍

此服務提供：

- 使用者註冊
- 使用者登入
- JWT 驗證（Access Token）
- Access Token 刷新
- 登出與 Token 黑名單
- 取得目前登入使用者資訊

本機開發位址：

- `http://localhost:18000`

API 前綴：

- `http://localhost:18000/api/v1`

Swagger 文件：

- `http://localhost:18000/docs`

OpenAPI JSON：

- `http://localhost:18000/openapi.json`

## 2. 前端啟動前檢查

1. 確認後端服務已啟動。
2. 開啟 `http://localhost:18000/health`，確認狀態正常。
3. 開啟 `http://localhost:18000/docs`，確認可看到 auth 端點。
4. 設定前端環境變數（範例）：

```bash
VITE_API_BASE_URL=http://localhost:18000/api/v1
```

## 3. Authentication API 合約

所有認證端點都在 `/api/v1/auth`。

### 3.1 註冊

- Method：`POST`
- Path：`/api/v1/auth/register`
- 是否需要登入：否

Request Body：

```json
{
  "email": "john@example.com",
  "username": "john_doe",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

欄位驗證重點：

- `email`：必須是合法 email
- `username`：3 到 100 字元
- `password`：至少 8 字元
- `full_name`：可選，最多 255 字元
- 密碼會使用 bcrypt 雜湊，若 UTF-8 位元組長度過長可能回傳 400

成功回應：

- Status：`201 Created`

範例回應：

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

常見錯誤：

- `400`：email 或 username 重複
- `422`：欄位缺漏或格式不正確

### 3.2 登入

- Method：`POST`
- Path：`/api/v1/auth/login`
- 是否需要登入：否

Request Body：

```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```

成功回應：

- Status：`200 OK`

範例回應：

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

常見錯誤：

- `401`：帳密錯誤或 Token 相關驗證失敗
- `429`：登入失敗次數過多，帳號暫時鎖定
- `422`：請求格式不符

### 3.3 取得目前使用者

- Method：`GET`
- Path：`/api/v1/auth/me`
- 是否需要登入：是（`Authorization: Bearer <access_token>`）

成功回應：

- Status：`200 OK`
- 回應結構與 login 回傳的 `user` 相同

常見錯誤：

- `403`：未帶 Bearer Token
- `401`：Token 無效、過期或已列入黑名單

### 3.4 刷新 Access Token

- Method：`POST`
- Path：`/api/v1/auth/refresh`
- 是否需要登入：否（以 body 傳 refresh token）

Request Body：

```json
{
  "refresh_token": "<jwt_refresh_token>"
}
```

成功回應：

- Status：`200 OK`

```json
{
  "access_token": "<new_access_token>",
  "token_type": "bearer"
}
```

常見錯誤：

- `401`：refresh token 過期、無效、型別錯誤或已黑名單
- `422`：請求格式不符

### 3.5 登出

- Method：`POST`
- Path：`/api/v1/auth/logout`
- 是否需要登入：是（`Authorization: Bearer <access_token>`）

Request Body：

```json
{
  "refresh_token": "<jwt_refresh_token>"
}
```

成功回應：

- Status：`200 OK`

```json
{
  "message": "Logged out successfully"
}
```

行為說明：

- 目前的 access token 與 refresh token 都會加入 Redis 黑名單（有 TTL）。
- 加入黑名單後，該 token 應視為立即失效。

## 4. 前端完整登入流程

### 4.1 首次登入流程

1. 使用者輸入帳號密碼。
2. 前端呼叫 `POST /auth/login`。
3. 前端保存 `access_token` 與 `refresh_token`。
4. 視需求呼叫 `GET /auth/me` 初始化使用者狀態。
5. 導向登入後頁面。

### 4.2 已登入請求流程

1. 讀取 `access_token`。
2. 在 Header 附上 `Authorization: Bearer <access_token>`。
3. 若 API 回 `200`，正常處理。
4. 若 API 回 `401`，執行一次 refresh 流程。

### 4.3 Refresh 流程

1. 以 `refresh_token` 呼叫 `POST /auth/refresh`。
2. 成功時更新 `access_token`，並重送原請求一次。
3. 失敗時清空本地登入狀態並導回登入頁。

### 4.4 登出流程

1. 呼叫 `POST /auth/logout`，同時傳入：
- Header 的 access token
- Body 的 refresh token
2. 不論 API 成功或失敗，都清空本地 token 與使用者狀態。
3. 導回登入頁。

## 5. 前端 Token 儲存建議

建議做法：

- access token：記憶體儲存或短期儲存
- refresh token：若架構允許，優先使用 HttpOnly Cookie

若使用 localStorage 或 sessionStorage，請至少確保：

- 已有 XSS 防護
- Token 生命週期處理完整
- 登出與 refresh 失敗時確實清除 token

## 6. 錯誤處理對照表

| HTTP | 典型原因 | 前端建議處理 |
|---|---|---|
| 400 | 商業規則錯誤（如帳號重複、密碼位元組過長） | 顯示可理解錯誤訊息 |
| 401 | Token 無效/過期或帳密錯誤 | 先 refresh 一次，仍失敗則強制重登入 |
| 403 | Authorization Header 缺失 | 檢查 request interceptor |
| 404 | 資源或使用者不存在 | 顯示 not found 狀態 |
| 422 | 欄位驗證失敗 | 映射至表單欄位錯誤 |
| 429 | 連續登入失敗導致鎖定 | 顯示鎖定提示，稍後再試 |
| 500 | 伺服器未預期錯誤 | 顯示通用錯誤並記錄事件 |

## 7. 請求範例

### cURL：登入

```bash
curl -X POST "http://localhost:18000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123!"
  }'
```

### cURL：取得目前使用者

```bash
curl -X GET "http://localhost:18000/api/v1/auth/me" \
  -H "Authorization: Bearer <access_token>"
```

### cURL：刷新 Token

```bash
curl -X POST "http://localhost:18000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<refresh_token>"
  }'
```

## 8. 後端改動時前端必查項目

若後端改動，請先確認以下是否受影響：

1. Endpoint path 或 method 是否改變
2. Request 必填欄位是否改變
3. Response schema 是否改變（含 `user` 內部欄位）
4. 錯誤碼是否改變
5. Token TTL 是否改變

若有任何改變，前端至少需同步更新：

- API client 型別與介面
- 表單驗證規則
- auth interceptor 與 refresh 邏輯
- 使用者狀態正規化流程

## 9. 前端每次發版建議驗證場景

1. 註冊成功與重複帳號失敗
2. 登入成功與錯誤密碼失敗
3. 無 token 存取保護端點（`403`）
4. 過期 token 存取保護端點（`401` 後 refresh）
5. 無效 refresh token（`401`，強制登出）
6. 登出後重用舊 token（`401`）
7. 多次登入失敗達鎖定（`429`）
