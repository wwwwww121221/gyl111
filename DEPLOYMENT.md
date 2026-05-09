# Supply Chain Agent 部署文档

本文档说明了如何从零开始部署“供应链智能管理系统”（包含前后端和数据库）。由于项目经历了多轮迭代，数据库表结构和字段可能与最早期版本有所不同，请严格按照本文档的说明进行部署和初始化。

## 1. 环境准备

确保部署服务器或本地开发环境已安装以下基础组件：

- **Python**: 3.10+ (推荐 3.11)
- **Node.js**: 16+ (推荐 18 LTS)
- **PostgreSQL**: 14+ (推荐 16)

---

## 2. 数据库配置与初始化

项目使用 PostgreSQL 作为关系型数据库。
由于系统在开发过程中新增了许多表（如历史采购订单 `PurchaseOrderHistory`、物料表 `Material`，以及表字段如 `inquiry_tasks.type`），**推荐使用一个干净的新数据库**，或者确保连接的数据库之前没有冲突的旧表。

1. **创建数据库**:
   打开 PostgreSQL (如通过 pgAdmin 或 psql)，创建一个新数据库：
   ```sql
   CREATE DATABASE supply_chain_agent;
   ```

2. **配置环境变量**:
   在项目根目录下创建一个 `.env` 文件（可以参考现有的 `.env`），配置数据库连接和超级管理员账号。
   
   示例 `.env` 文件内容：
   ```env
   # LLM大模型配置 (用于智能比价等AI功能)
   LLM_PROVIDER=openai
   LLM_API_KEY=sk-xxxxxx
   LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   LLM_MODEL=qwen-plus

   # 数据库连接 (用户名:密码@主机:端口/数据库名)
   DATABASE_URL=postgresql://postgres:1234@localhost:5432/supply_chain_agent

   # 系统初始超级管理员账号 (系统第一次启动时会自动创建该账号)
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=123456
   ```

3. **表结构自动生成**:
   项目的后端使用 SQLAlchemy。当你第一次启动后端服务时，`main.py` 会自动执行 `Base.metadata.create_all(bind=engine)`，它会**自动扫描所有的模型定义并生成最新的表结构**。
   *(注：如果后续还在旧库上进行开发并修改了字段，由于 `create_all` 不会自动修改已存在的表，你需要手动删表或使用 `ALTER TABLE` 语句更新字段。对于新部署，直接连接空数据库即可。)*

---

## 3. 后端服务部署 (FastAPI)

后端使用了 FastAPI 框架。

1. **进入项目根目录**:
   打开终端（如 PowerShell 或 CMD）。
   ```bash
   cd D:\Supply_chain_agent
   ```

2. **创建并激活虚拟环境**:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux / macOS:
   # source venv/bin/activate
   ```

3. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```

4. **启动后端服务**:
   ```bash
   # 使用 uvicorn 启动
   python main.py
   # 或者
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *启动后，后端将在 `http://localhost:8000` 运行。*
   *并且系统会自动创建 `.env` 中配置的管理员账号，同时初始化定时任务（如金蝶 ERP 同步任务）。*

---

## 4. 前端服务部署 (Vue 3 + Vite)

前端采用 Vue 3 (Composition API) + Vite 构建。

1. **进入前端目录**:
   保持后端运行，另开一个终端窗口。
   ```bash
   cd D:\Supply_chain_agent\frontend
   ```

2. **安装依赖**:
   ```bash
   npm install
   ```

3. **本地开发运行**:
   ```bash
   npm run dev
   ```
   *启动后，前端将在 `http://localhost:5173` 运行。打开浏览器即可访问系统登录页。*

4. **生产环境构建**:
   如果要部署到线上（如 Nginx），需执行：
   ```bash
   npm run build
   ```
   然后将生成的 `dist` 目录放到 Web 服务器中，并配置反向代理将 `/api` 的请求转发给 `http://localhost:8000`。

---

## 5. 常见问题排查

- **端口冲突**: 
  如果启动后端时提示 `[WinError 10048] 通常每个套接字地址(协议/网络地址/端口)只允许使用一次`，说明 8000 端口被占用。可以执行 `taskkill /F /IM python.exe` 关闭残留的进程。
- **数据库类型错误**:
  如果遇到类似 `can't compare datetime.datetime to datetime.date` 或缺少某列（如 `type` column missing）的报错，是因为连接了旧版的数据库结构。最快的解决方法是**直接 Drop 原有数据库**并重新 Create，然后重启后端让 ORM 重新建表。
- **无法同步 ERP 数据**:
  检查 `kingdee_erp_tool/conf.ini` 或代码内的 ERP 配置 (URL、DB_ID、APP_ID 等) 是否正确且可访问。
