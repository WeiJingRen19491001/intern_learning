# LUMI 智能客服 Agent

## 项目概述
基于阿里云百炼平台和 FastAPI 开发的智能客服系统。

## 目录结构
- `backend/`: 后端服务 (FastAPI)
- `frontend/`: 前端界面
- `db_init/`: 数据库初始化脚本
- `docker-compose.yaml`: 容器编排

## 快速开始

### 1. 环境配置
复制 `.env.example` 为 `.env` 并填入 API Key。
```bash
cp .env.example .env
```

### 2. 启动服务 (Docker)
```bash
docker-compose up --build
```

### 3. 本地开发
#### 创建虚拟环境
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

#### 安装依赖
```bash
pip install -r backend/requirements.txt
```

#### 启动后端
```bash
cd backend
python -m uvicorn app.main:app --reload
```
