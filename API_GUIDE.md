# 登錄服務 API 文檔

## 快速開始

### 1. 啟動服務

使用 Docker Compose：
```bash
docker-compose up -d
```

預設主機埠為 `18000`（可在 `.env` 用 `APP_HOST_PORT` 修改），避免占用本機 `8000`。

檢查服務健康狀態：
```bash
curl http://localhost:18000/health
```

交互式文檔：http://localhost:18000/docs

### 2. 註冊新用戶

```bash
curl -X POST "http://localhost:18000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "username": "john_doe",
    "password": "SecurePass123!",
    "full_name": "John Doe"
  }'
```

### 3. 登錄

```bash
curl -X POST "http://localhost:18000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123!"
  }'
```

響應包含 `access_token` 和 `refresh_token`

### 4. 使用令牌訪問受保護資源

```bash
curl -X GET "http://localhost:18000/api/v1/auth/me" \
  -H "Authorization: Bearer {your_access_token}"
```

### 5. 刷新令牌

```bash
curl -X POST "http://localhost:18000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "{your_refresh_token}"
  }'
```

### 6. 登出

```bash
curl -X POST "http://localhost:18000/api/v1/auth/logout" \
  -H "Authorization: Bearer {your_access_token}"
```

## 架構說明

### 為什麼選擇 PostgreSQL + Redis？

#### PostgreSQL（靜態用戶數據）
**優點**
- ACID 事務保證數據一致性
- 強大的查詢能力（複雜的用戶查詢）
- 數據持久化和備份
- 支持複雜的關係

**存儲內容**
- 用戶身份信息（email、username、密碼哈希）
- 用戶資料（名稱、創建時間等）
- 用戶狀態（是否激活、驗證狀態）

#### Redis（動態會話和狀態）
**優點**
- 超快速讀寫（內存型數據庫）
- 自動過期機制（TTL）
- 原子操作（確保計數器準確）
- 支持多種數據結構

**存儲內容**
- 用戶會話（session_id → user_id，24h 過期）
- 登錄嘗試計數（防暴力破解）
- 臨時緩存數據

### 數據流示例

**登錄流程：**
```
1. 用戶發送登錄請求 → API
2. API 查詢 PostgreSQL 驗證用戶身份
3. 檢查 Redis 中的登錄嘗試次數 → 檢查是否被鎖定
4. 如驗證成功：
   - 清除 Redis 中的登錄嘗試計數
   - 生成 JWT Token
   - 返回 access_token 和 refresh_token
5. 如驗證失敗：
   - 增加 Redis 中的嘗試計數
   - 如果超過 5 次，鎖定賬戶 15 分鐘
   - 返回 401 錯誤
```

**訪問受保護資源：**
```
1. 用戶發送請求 + access_token → API
2. API 驗證 JWT Token 簽名和有效期
3. 如有效：提取 sub（user_id）並繼續處理
4. 如無效：返回 401 Unauthorized
```

## 代碼組織

### 核心模塊

**app/core/** - 配置和異常
```
config.py      - 應用配置（從環境變量讀取）
exceptions.py  - 自定義異常類
logging.py     - 日誌配置
```

**app/database/** - 數據庫連接
```
connection.py  - PostgreSQL 連接和會話管理
redis.py       - Redis 單例客戶端（Singleton Pattern）
```

**app/models/** - SQLAlchemy 模型
```
user.py        - User 表結構
```

**app/schemas/** - Pydantic 驗證模型
```
user.py        - 請求/響應 DTO
```

**app/services/** - 業務邏輯層
```
user_service.py   - 用戶註冊、身份驗證、查詢
auth_service.py   - 會話、令牌、登錄嘗試管理
```

**app/routers/** - API 端點
```
auth.py        - 認證相關 API 端點
```

**app/utils/** - 工具函數
```
security.py    - 密碼哈希、JWT 操作
```

## 設計模式

### 1. 單例模式（Singleton）
Redis 客戶端使用單例模式確保整個應用只有一個連接。

```python
class RedisClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### 2. 依賴注入（Dependency Injection）
FastAPI 的 `Depends` 用於自動注入依賴。

```python
@app.get("/me")
async def get_current_user(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ...
```

### 3. 工廠模式（Factory Pattern）
StatelessUser 模型有工廠方法。

### 4. 策略模式（Strategy Pattern）
不同的驗證策略（密碼驗證、令牌驗證）

## 安全最佳實踐

### 1. 密碼安全
✅ bcrypt 12 輪加鹽
✅ 密碼不存儲為明文
✅ 強密碼要求（最少 8 字符）

### 2. 令牌安全
✅ JWT 帶有簽名驗證
✅ 短期訪問令牌（30 分鐘）
✅ 長期刷新令牌（7 天）
✅ token_type 字段防止混淆

### 3. 暴力破解防護
✅ 登錄嘗試計數
✅ 5 次失敗後鎖定 15 分鐘
✅ Redis TTL 自動解鎖

### 4. 速率限制
可添加 SlowAPI 進行速率限制

### 5. 日誌和監控
✅ 所有身份驗證操作都被記錄
✅ 包含用戶 ID 和時間戳

## 常見擴展

### 添加電子郵件驗證
```python
# 在 User 模型添加 email_verified 字段
# 在 Redis 存儲驗證碼
# 發送驗證郵件
```

### 添加 OAuth 2.0
```python
# 集成 google、github 等提供商
# 通過 authlib 或 python-jose
```

### 添加角色和權限
```python
# 添加 Role 模型
# 在路由上使用 Role 檢查依賴
```

### 添加審計日誌
```python
# 添加 AuditLog 模型
# 記錄所有重要操作
```

## 監控和調試

### 查看 PostgreSQL 日誌
```bash
docker-compose logs postgres
```

### 查看 Redis 日誌
```bash
docker-compose logs redis
```

### 查看應用日誌
```bash
docker-compose logs app
```

### 進入 PostgreSQL 容器
```bash
docker-compose exec postgres psql -U user -d auth_service
```

### 進入 Redis 容器
```bash
docker-compose exec redis redis-cli
```

## 性能優化

1. **數據庫**
   - 在常用字段上建立索引（email、username）
   - 使用連接池

2. **緩存**
   - 緩存用戶資料（使用 Redis）
   - 實施查詢結果緩存

3. **令牌**
   - 實施令牌黑名單（用於登出）
   - 將長期會話遷移到 Redis

## 故障排除

### 連接拒絕
檢查 Docker 容器是否運行：
```bash
docker-compose ps
```

### 數據庫錯誤
檢查 PostgreSQL 日誌並確保漷移已運行

### 認證失敗
- 檢查 SECRET_KEY 是否正確設置
- 驗證令牌未過期
- 檢查用戶是否激活

