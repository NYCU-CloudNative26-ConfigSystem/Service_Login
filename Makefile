.PHONY: help install install-dev up up-infra down logs shell test coverage lint format clean

help:
	@echo "登錄微服務 - 可用命令"
	@echo ""
	@echo "安裝和設置："
	@echo "  make install         - 安裝生產依賴"
	@echo "  make install-dev     - 安裝開發依賴"
	@echo "  make up              - 啟動 Docker 容器"
	@echo "  make up-infra        - 只啟動 PostgreSQL/Redis（不啟動 app）"
	@echo "  make down            - 停止 Docker 容器"
	@echo ""
	@echo "開發："
	@echo "  make logs            - 查看應用日誌"
	@echo "  make shell           - 進入應用容器"
	@echo "  make test            - 運行測試"
	@echo "  make coverage        - 生成測試覆蓋率報告"
	@echo ""
	@echo "代碼質量："
	@echo "  make lint            - 運行 flake8 和 mypy"
	@echo "  make format          - 格式化代碼（black, isort）"
	@echo "  make clean           - 清理臨時文件"
	@echo ""
	@echo "數據庫："
	@echo "  make db-shell        - 進入 PostgreSQL"
	@echo "  make redis-shell     - 進入 Redis"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

up:
	docker-compose up -d

up-infra:
	docker-compose up -d postgres redis

down:
	docker-compose down

logs:
	docker-compose logs -f app

shell:
	docker-compose exec app bash

test:
	pytest tests/ -v

coverage:
	pytest tests/ --cov=app --cov-report=html --cov-report=term
	@echo "Coverage 報告在 htmlcov/index.html"

lint:
	flake8 app tests --max-line-length=100
	mypy app --ignore-missing-imports

format:
	black app tests --line-length=100
	isort app tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true

db-shell:
	docker-compose exec postgres psql -U user -d auth_service

redis-shell:
	docker-compose exec redis redis-cli

migrate:
	docker-compose exec app alembic upgrade head

migrate-down:
	docker-compose exec app alembic downgrade -1

migrate-new:
	docker-compose exec app alembic revision --autogenerate -m "$(message)"

dev:
	docker-compose up -d postgres redis
	uvicorn main:app --reload --host 0.0.0.0 --port $${APP_PORT:-18000}

req-freeze:
	pip freeze > requirements-full.txt
