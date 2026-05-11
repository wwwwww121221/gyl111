from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.config import settings
from routers import auth, erp_sync, inquiry, supplier, warning, contract, template, material, system, compare
from models import Base, engine, ensure_runtime_schema_columns
import traceback
import os
from models import SessionLocal, User
from core.security import get_password_hash
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.sync_materials import sync_materials
from backend.sync_suppliers import sync_suppliers
from backend.sync_po_history import sync_po_history
import logging
from datetime import datetime, timedelta

# 初始化调度器
scheduler = AsyncIOScheduler()

# 初始化数据库
# 注意：在生产环境中通常使用 Alembic 进行迁移，这里为了简单直接创建
Base.metadata.create_all(bind=engine)
ensure_runtime_schema_columns()

def ensure_admin_user():
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        return
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == username).first()
        if not exists:
            u = User(username=username, password_hash=get_password_hash(password), role="admin")
            db.add(u)
            db.commit()
    finally:
        db.close()

ensure_admin_user()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting up... Setting up scheduled tasks.")
    # Add scheduled tasks
    scheduler.add_job(sync_materials, 'cron', hour=2, minute=0, id='daily_material_sync')
    scheduler.add_job(sync_suppliers, 'cron', hour=2, minute=30, id='daily_supplier_sync')
    # 每天凌晨 3 点增量同步一次采购订单数据，默认从过去 3 天的数据开始同步以防遗漏
    scheduler.add_job(
        lambda: sync_po_history(start_date=(datetime.now() - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00")),
        'cron',
        hour=3,
        minute=0,
        id='daily_po_history_sync'
    )
    scheduler.start()
    yield
    logging.info("Shutting down... Stopping scheduled tasks.")
    scheduler.shutdown()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Exception Handler Middleware
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        print(f"Unhandled exception: {e}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error": str(e)})

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境请修改为前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(erp_sync.router, prefix=f"{settings.API_V1_STR}/erp", tags=["ERP"])
app.include_router(inquiry.router, prefix=f"{settings.API_V1_STR}/inquiry", tags=["Inquiry"])
app.include_router(supplier.router, prefix=f"{settings.API_V1_STR}/supplier", tags=["Supplier"])
app.include_router(warning.router, prefix=f"{settings.API_V1_STR}/warning", tags=["Warning"])
app.include_router(contract.router, prefix=f"{settings.API_V1_STR}/contract", tags=["Contract"])
app.include_router(template.router, prefix=f"{settings.API_V1_STR}/template", tags=["Template"])
app.include_router(material.router, prefix=f"{settings.API_V1_STR}/material", tags=["Material"])
app.include_router(system.router, prefix=f"{settings.API_V1_STR}/system", tags=["System"])
app.include_router(compare.router, prefix=f"{settings.API_V1_STR}/compare", tags=["Compare"])

@app.get("/")
def root():
    return {"message": "Welcome to Supply Chain Agent API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
