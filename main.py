from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.config import settings
from routers import auth, erp_sync, inquiry, supplier, warning, contract, template, material, system, compare, assessment
from models import Base, engine, ensure_runtime_schema_columns, backfill_supplier_memberships, seed_assessment_items
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
import hashlib
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from services.wechat_service import (
    build_wechat_frontend_route_url,
    build_wechat_oauth_authorize_url,
    build_wechat_subscribe_welcome_message,
    build_wechat_text_reply,
    dispatch_quote_deadline_reminders,
    get_wechat_oauth_openid,
    is_wechat_configured,
)

# 初始化调度器
scheduler = AsyncIOScheduler()

# 初始化数据库
# 注意：在生产环境中通常使用 Alembic 进行迁移，这里为了简单直接创建
Base.metadata.create_all(bind=engine)
ensure_runtime_schema_columns()
backfill_supplier_memberships()
seed_assessment_items()

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


def run_wechat_deadline_reminder_job():
    db = SessionLocal()
    try:
        dispatch_quote_deadline_reminders(db)
    finally:
        db.close()

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
    scheduler.add_job(
        run_wechat_deadline_reminder_job,
        'interval',
        minutes=30,
        id='wechat_quote_deadline_reminder'
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
app.include_router(assessment.router, prefix=f"{settings.API_V1_STR}/assessment", tags=["Assessment"])

@app.get("/")
def root():
    return {"message": "Welcome to Supply Chain Agent API"}

@app.get("/wechat/verify")
async def wechat_verify(
    signature: str | None = Query(default=None),
    timestamp: str | None = Query(default=None),
    nonce: str | None = Query(default=None),
    echostr: str | None = Query(default=None),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
):
    if code:
        try:
            openid = get_wechat_oauth_openid(code)
        except Exception as exc:
            return JSONResponse(status_code=400, content={"detail": str(exc)})

        frontend_base = str(settings.WECHAT_OAUTH_FRONTEND_URL or "").strip()
        if frontend_base:
            target_path = "/login" if state != "register" else "/register"
            redirect_url = build_wechat_frontend_route_url(target_path, {"openid": openid})
            return RedirectResponse(url=redirect_url)

        return JSONResponse(content={"openid": openid, "state": state or "login"})

    if not signature or not timestamp or not nonce or echostr is None:
        return PlainTextResponse(content="", status_code=400)

    tmp_arr = [settings.WECHAT_TOKEN, timestamp, nonce]
    tmp_arr.sort()
    tmp_str = "".join(tmp_arr)
    tmp_str_hash = hashlib.sha1(tmp_str.encode("utf-8")).hexdigest()
    if tmp_str_hash == signature:
        return PlainTextResponse(content=echostr)
    return PlainTextResponse(content="", status_code=403)


@app.post("/wechat/verify")
async def wechat_event_callback(
    request: Request,
    signature: str | None = Query(default=None),
    timestamp: str | None = Query(default=None),
    nonce: str | None = Query(default=None),
):
    if not signature or not timestamp or not nonce:
        return PlainTextResponse(content="", status_code=400)

    tmp_arr = [settings.WECHAT_TOKEN, timestamp, nonce]
    tmp_arr.sort()
    tmp_str = "".join(tmp_arr)
    tmp_str_hash = hashlib.sha1(tmp_str.encode("utf-8")).hexdigest()
    if tmp_str_hash != signature:
        return PlainTextResponse(content="", status_code=403)

    raw_body = await request.body()
    if not raw_body:
        return PlainTextResponse(content="success")

    try:
        root = ET.fromstring(raw_body)
    except ET.ParseError:
        return PlainTextResponse(content="success")

    msg_type = (root.findtext("MsgType") or "").strip()
    from_user = (root.findtext("FromUserName") or "").strip()
    to_user = (root.findtext("ToUserName") or "").strip()
    event = (root.findtext("Event") or "").strip().lower()

    if msg_type == "event" and event == "subscribe" and from_user and to_user:
        welcome_message = build_wechat_subscribe_welcome_message(from_user)
        if welcome_message:
            reply_xml = build_wechat_text_reply(
                to_user=from_user,
                from_user=to_user,
                content=welcome_message,
            )
            return PlainTextResponse(content=reply_xml, media_type="application/xml")

    return PlainTextResponse(content="success")


@app.get("/wechat/oauth/start")
async def wechat_oauth_start(
    target: str = Query(default="login"),
):
    if not is_wechat_configured():
        return JSONResponse(status_code=400, content={"detail": "微信公众号配置未完成"})

    redirect_uri = str(settings.WECHAT_OAUTH_REDIRECT_URL or settings.WECHAT_VERIFY_URL or "").strip()
    if not redirect_uri:
        return JSONResponse(status_code=400, content={"detail": "缺少 WECHAT_VERIFY_URL 配置"})

    try:
        auth_url = build_wechat_oauth_authorize_url(redirect_uri=redirect_uri, state=target)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    return RedirectResponse(url=auth_url)


@app.get("/wechat/oauth/debug")
async def wechat_oauth_debug(
    target: str = Query(default="login"),
):
    redirect_uri = str(settings.WECHAT_OAUTH_REDIRECT_URL or settings.WECHAT_VERIFY_URL or "").strip()
    auth_url = None
    error = None
    if redirect_uri:
        try:
            auth_url = build_wechat_oauth_authorize_url(redirect_uri=redirect_uri, state=target)
        except Exception as exc:
            error = str(exc)

    return JSONResponse(
        content={
            "app_id": settings.WECHAT_APP_ID,
            "verify_url": settings.WECHAT_VERIFY_URL,
            "oauth_redirect_url": settings.WECHAT_OAUTH_REDIRECT_URL,
            "oauth_frontend_url": settings.WECHAT_OAUTH_FRONTEND_URL,
            "redirect_uri_used_for_wechat": redirect_uri,
            "authorize_url": auth_url,
            "error": error,
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
