from __future__ import annotations

import logging
import json
import hashlib
from datetime import datetime
from typing import Iterable, Optional
from urllib.parse import urlencode, urlparse

import requests
from sqlalchemy.orm import Session

from core.config import settings
from core.redis_client import cache_clear_pattern, cache_delete, cache_get, cache_set
from models import Contract, InquirySupplier, InquiryTask, LinkStatus, Supplier, SupplierMember, TaskStatus, User

logger = logging.getLogger(__name__)

WECHAT_ACCESS_TOKEN_CACHE_KEY = "wechat:access_token"
WECHAT_TEMPLATE_COLOR = "#173177"
WECHAT_DEADLINE_REMINDER_CACHE_PREFIX = "wechat:deadline-reminder"
WECHAT_MENU_KEY_LOGIN = "SUPPLIER_LOGIN_BIND"
WECHAT_MENU_KEY_REGISTER = "SUPPLIER_ACCOUNT_REGISTER"


def _wrap_template_value(value: object) -> dict[str, str]:
    return {
        "value": "" if value is None else str(value),
        "color": WECHAT_TEMPLATE_COLOR,
    }


def is_wechat_configured() -> bool:
    return bool(settings.WECHAT_APP_ID and settings.WECHAT_APP_SECRET and settings.WECHAT_TOKEN)


def _get_wechat_access_token_cache_key() -> str:
    app_id = str(settings.WECHAT_APP_ID or "").strip()
    app_secret = str(settings.WECHAT_APP_SECRET or "").strip()
    if not app_id:
        return WECHAT_ACCESS_TOKEN_CACHE_KEY

    secret_hash = hashlib.sha1(app_secret.encode("utf-8")).hexdigest()[:12] if app_secret else "no-secret"
    return f"{WECHAT_ACCESS_TOKEN_CACHE_KEY}:{app_id}:{secret_hash}"


def get_wechat_access_token(force_refresh: bool = False) -> str:
    if not is_wechat_configured():
        raise RuntimeError("微信公众号配置未完成")

    cache_key = _get_wechat_access_token_cache_key()
    if force_refresh:
        cache_clear_pattern(f"{WECHAT_ACCESS_TOKEN_CACHE_KEY}*")
        cache_delete(WECHAT_ACCESS_TOKEN_CACHE_KEY, cache_key)

    if not force_refresh:
        cached = cache_get(cache_key)
        if isinstance(cached, dict):
            token = str(cached.get("access_token") or "").strip()
            if token:
                return token

    response = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={
            "grant_type": "client_credential",
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errcode"):
        raise RuntimeError(f"获取微信公众号 access_token 失败: {payload}")

    access_token = str(payload.get("access_token") or "").strip()
    expires_in = int(payload.get("expires_in") or 7200)
    if not access_token:
        raise RuntimeError(f"微信公众号 access_token 响应无效: {payload}")

    cache_set(
        cache_key,
        {"access_token": access_token},
        ttl=max(expires_in - 300, 60),
    )
    return access_token


def send_template_message(
    openid: str,
    template_id: str,
    data: dict[str, dict[str, str]],
    url: Optional[str] = None,
) -> dict:
    normalized_openid = str(openid or "").strip()
    normalized_template_id = str(template_id or "").strip()
    if not normalized_openid:
        raise RuntimeError("缺少接收人 openid")
    if not normalized_template_id:
        raise RuntimeError("缺少模板 ID")

    payload = {
        "touser": normalized_openid,
        "template_id": normalized_template_id,
        "data": data,
    }
    if url:
        payload["url"] = url

    for attempt in range(2):
        access_token = get_wechat_access_token(force_refresh=attempt > 0)
        response = requests.post(
            "https://api.weixin.qq.com/cgi-bin/message/template/send",
            params={"access_token": access_token},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        errcode = int(result.get("errcode") or 0)
        if errcode == 0:
            return result
        if errcode in {40001, 42001} and attempt == 0:
            logger.info("微信公众号 access_token 已失效，刷新后重试")
            continue
        raise RuntimeError(f"发送微信公众号模板消息失败: {result}")

    raise RuntimeError("发送微信公众号模板消息失败")


def build_wechat_oauth_authorize_url(redirect_uri: str, state: str = "login") -> str:
    if not settings.WECHAT_APP_ID:
        raise RuntimeError("微信公众号 AppID 未配置")
    query = urlencode(
        {
            "appid": settings.WECHAT_APP_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "snsapi_base",
            "state": state or "login",
        }
    )
    return f"https://open.weixin.qq.com/connect/oauth2/authorize?{query}#wechat_redirect"


def get_wechat_oauth_openid(code: str) -> str:
    normalized_code = str(code or "").strip()
    if not normalized_code:
        raise RuntimeError("缺少微信 OAuth code")

    response = requests.get(
        "https://api.weixin.qq.com/sns/oauth2/access_token",
        params={
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
            "code": normalized_code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errcode"):
        raise RuntimeError(f"获取微信 openid 失败: {payload}")

    openid = str(payload.get("openid") or "").strip()
    if not openid:
        raise RuntimeError(f"微信 openid 响应无效: {payload}")
    return openid


def collect_user_openids(users: Iterable[User]) -> list[str]:
    openids: list[str] = []
    seen: set[str] = set()
    for user in users:
        if not user:
            continue
        openid = str(user.openid or "").strip()
        if not openid or openid in seen:
            continue
        seen.add(openid)
        openids.append(openid)
    return openids


def collect_supplier_openids(
    db: Session,
    supplier: Supplier,
    include_pending: bool = False,
) -> list[str]:
    if not supplier:
        return []

    users: list[User] = []
    if supplier.user:
        users.append(supplier.user)

    allowed_statuses = ["active"]
    if include_pending:
        allowed_statuses.append("pending")

    member_rows = (
        db.query(SupplierMember)
        .filter(
            SupplierMember.supplier_id == supplier.id,
            SupplierMember.status.in_(allowed_statuses),
        )
        .all()
    )
    for member in member_rows:
        if member.user:
            users.append(member.user)

    return collect_user_openids(users)


def _batch_send_template_message(
    openids: Iterable[str],
    template_id: str,
    data: dict[str, dict[str, str]],
    url: Optional[str] = None,
) -> dict[str, object]:
    success_openids: list[str] = []
    failed: list[dict[str, str]] = []

    for openid in openids:
        try:
            send_template_message(openid=openid, template_id=template_id, data=data, url=url)
            success_openids.append(openid)
        except Exception as exc:
            logger.exception("微信公众号模板消息发送失败, openid=%s", openid)
            failed.append({"openid": openid, "error": str(exc)})

    return {
        "sent_count": len(success_openids),
        "failed_count": len(failed),
        "success_openids": success_openids,
        "failed": failed,
    }


def _format_dt(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    normalized = str(value or "").strip()
    return normalized or "-"


def _resolve_template_url(url: Optional[str] = None) -> Optional[str]:
    normalized = str(url or settings.WECHAT_TEMPLATE_DEFAULT_URL or "").strip()
    if normalized:
        return normalized

    try:
        return build_wechat_frontend_route_url("/login")
    except Exception:
        return None


def _build_supplier_portal_url(path: str, query: Optional[dict[str, str]] = None) -> Optional[str]:
    try:
        return build_wechat_frontend_route_url(path, query)
    except Exception:
        return _resolve_template_url()


def _get_inquiry_supplier_link_id(db: Session, task: InquiryTask, supplier: Supplier) -> Optional[int]:
    if not task or not supplier:
        return None

    link = (
        db.query(InquirySupplier)
        .filter(
            InquirySupplier.task_id == task.id,
            InquirySupplier.supplier_id == supplier.id,
        )
        .first()
    )
    return int(link.id) if link else None


def _build_supplier_inquiry_url(
    db: Session,
    task: InquiryTask,
    supplier: Supplier,
    action: str = "detail",
) -> Optional[str]:
    link_id = _get_inquiry_supplier_link_id(db, task, supplier)
    query: dict[str, str] = {}
    if link_id:
        query["inquiry_supplier_id"] = str(link_id)
    if action:
        query["action"] = action
    if task and task.id:
        query["task_id"] = str(task.id)
    return _build_supplier_portal_url("/supplier/inquiries", query or None)


def _collect_task_project_labels(task: InquiryTask) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for item in task.items or []:
        request = getattr(item, "request", None)
        project_info = getattr(request, "project_info", None) or {}
        for raw_value in (project_info.get("name"), project_info.get("number")):
            normalized = str(raw_value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            labels.append(normalized)
    return labels


def _get_task_project_label(task: InquiryTask) -> str:
    labels = _collect_task_project_labels(task)
    if labels:
        return "、".join(labels[:3])
    return str(task.title or "").strip() or "-"


def _get_task_material_label(task: InquiryTask) -> str:
    material_names: list[str] = []
    seen: set[str] = set()
    for item in task.items or []:
        request = getattr(item, "request", None)
        normalized = str(getattr(request, "material_name", "") or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        material_names.append(normalized)
    if not material_names:
        return "-"
    if len(material_names) == 1:
        return material_names[0]
    return f"{material_names[0]} 等{len(material_names)}项物料"


def _get_supplier_account_label(db: Session, supplier: Supplier) -> str:
    direct_username = str(getattr(getattr(supplier, "user", None), "username", "") or "").strip()
    if direct_username:
        return direct_username

    member_rows = (
        db.query(SupplierMember)
        .filter(
            SupplierMember.supplier_id == supplier.id,
            SupplierMember.status.in_(["active", "pending"]),
        )
        .all()
    )
    for member in member_rows:
        username = str(getattr(getattr(member, "user", None), "username", "") or "").strip()
        if username:
            return username
        member_name = str(getattr(member, "member_name", "") or "").strip()
        if member_name:
            return member_name

    return str(supplier.contact_person or supplier.phone or supplier.name or "-").strip() or "-"


def _get_task_buyer_unit_label(task: InquiryTask) -> str:
    buyer = getattr(task, "buyer", None)
    for raw_value in (
        getattr(buyer, "department", None),
        getattr(buyer, "username", None),
    ):
        normalized = str(raw_value or "").strip()
        if normalized:
            return normalized
    return "询价平台"


def _get_awarded_supplier_label(task: InquiryTask) -> str:
    supplier_names: list[str] = []
    seen: set[str] = set()
    for link in task.suppliers or []:
        if link.status != LinkStatus.DEAL:
            continue
        supplier_name = str(getattr(getattr(link, "supplier", None), "name", "") or "").strip()
        if not supplier_name or supplier_name in seen:
            continue
        seen.add(supplier_name)
        supplier_names.append(supplier_name)
    if not supplier_names:
        return "无"
    return "、".join(supplier_names[:3])


def _get_contract_buyer_label(db: Session, task: InquiryTask, supplier: Supplier) -> str:
    link = (
        db.query(InquirySupplier)
        .filter(
            InquirySupplier.task_id == task.id,
            InquirySupplier.supplier_id == supplier.id,
        )
        .first()
    )
    if link:
        contract = db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).first()
        if contract:
            normalized = str(contract.buyer_company_name or "").strip()
            if normalized:
                return normalized
    return _get_task_buyer_unit_label(task)


def get_wechat_public_base_url() -> str:
    verify_url = str(settings.WECHAT_VERIFY_URL or "").strip()
    if not verify_url:
        raise RuntimeError("Missing WECHAT_VERIFY_URL")

    parsed = urlparse(verify_url)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("Invalid WECHAT_VERIFY_URL")

    return f"{parsed.scheme}://{parsed.netloc}"


def get_wechat_frontend_base_url() -> str:
    frontend_base = str(
        settings.WECHAT_OAUTH_FRONTEND_URL
        or settings.WECHAT_TEMPLATE_DEFAULT_URL
        or ""
    ).strip()
    if not frontend_base:
        raise RuntimeError("Missing WECHAT_OAUTH_FRONTEND_URL")

    parsed = urlparse(frontend_base)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("Invalid WECHAT_OAUTH_FRONTEND_URL")

    return f"{parsed.scheme}://{parsed.netloc}"


def build_wechat_frontend_route_url(path: str, query: Optional[dict[str, str]] = None) -> str:
    normalized_path = f"/{str(path or '').strip().lstrip('/')}"
    query_string = urlencode({k: v for k, v in (query or {}).items() if v is not None and str(v).strip() != ""})
    route_url = f"{get_wechat_frontend_base_url().rstrip('/')}/#{normalized_path}"
    if query_string:
        route_url = f"{route_url}?{query_string}"
    return route_url


def build_wechat_bind_entry_url(openid: str | None = None, target: str = "login") -> str:
    normalized_target = "register" if str(target or "").strip().lower() == "register" else "login"
    target_path = "/register" if normalized_target == "register" else "/login"
    params: dict[str, str] = {}
    normalized_openid = str(openid or "").strip()
    if normalized_openid:
        params["openid"] = normalized_openid
    return build_wechat_frontend_route_url(target_path, params)


def build_wechat_oauth_entry_url(target: str = "login") -> str:
    normalized_target = "register" if str(target or "").strip().lower() == "register" else "login"
    redirect_url = str(settings.WECHAT_OAUTH_REDIRECT_URL or "").strip()
    base_url = (
        f"{urlparse(redirect_url).scheme}://{urlparse(redirect_url).netloc}"
        if redirect_url and urlparse(redirect_url).scheme and urlparse(redirect_url).netloc
        else get_wechat_public_base_url()
    ).rstrip("/")
    return f"{base_url}/wechat/oauth/start?target={normalized_target}"


def build_wechat_menu_payload() -> dict[str, object]:
    menu_version = str(settings.WECHAT_MENU_URL_VERSION or "").strip()
    homepage_url = build_wechat_frontend_route_url(
        "/login",
        {"menu_v": menu_version} if menu_version else None,
    )

    return {
        "button": [
            {
                "type": "view",
                "name": "\u5e73\u53f0\u767b\u5f55",
                "url": build_wechat_oauth_entry_url("login"),
            },
            {
                "type": "view",
                "name": "\u4f9b\u5e94\u5546\u5165\u9a7b",
                "url": build_wechat_oauth_entry_url("register"),
            },
            {
                "type": "view",
                "name": "\u5e73\u53f0\u9996\u9875",
                "url": homepage_url,
            },
        ]
    }


def build_wechat_menu_click_message(event_key: str, openid: str | None = None) -> str:
    normalized_key = str(event_key or "").strip()
    if normalized_key == WECHAT_MENU_KEY_REGISTER:
        register_url = build_wechat_oauth_entry_url(target="register")
        login_url = build_wechat_oauth_entry_url(target="login")
        return "\n".join(
            [
                "请先创建供应商账号。注册完成后，系统会进入同一个资料提交页面，可选择绑定已有供应商，或创建新供应商入驻申请。",
                f"供应商入驻：{register_url}",
                "",
                f"已有账号请直接登录：{login_url}",
            ]
        )

    login_url = build_wechat_oauth_entry_url(target="login")
    register_url = build_wechat_oauth_entry_url(target="register")
    return "\n".join(
        [
            "请登录供应链协同平台。内部人员可直接使用账号登录；供应商登录后可绑定已有供应商，或创建新供应商入驻申请。",
            f"平台登录：{login_url}",
            "",
            f"供应商没有账号请先入驻：{register_url}",
        ]
    )


def build_wechat_subscribe_welcome_message(openid: str | None = None) -> str:
    base_message = str(settings.WECHAT_SUBSCRIBE_WELCOME_MESSAGE or "").strip()

    lines = [base_message] if base_message else ["欢迎关注供应链协同平台。"]
    lines.extend(
        [
            "",
            "您可以在这里接收：",
            "1. 供应商入驻审核结果",
            "2. 新询价邀请",
            "3. 发货预警提醒",
            "4. 合同与报价相关通知",
            "",
            "请点击公众号底部菜单【平台登录】进入系统。内部人员可直接登录，供应商登录后可绑定已有供应商或创建新供应商入驻申请。",
            "供应商没有账号时，请点击【供应商入驻】先完成账号创建。",
        ]
    )
    return "\n".join(lines)
def get_wechat_menu() -> dict:
    access_token = get_wechat_access_token()
    response = requests.get(
        "https://api.weixin.qq.com/cgi-bin/get_current_selfmenu_info",
        params={"access_token": access_token},
        timeout=10,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("errcode"):
        raise RuntimeError(f"Failed to get WeChat menu: {result}")
    return result


def delete_wechat_menu() -> dict:
    for attempt in range(2):
        access_token = get_wechat_access_token(force_refresh=attempt > 0)
        response = requests.get(
            "https://api.weixin.qq.com/cgi-bin/menu/delete",
            params={"access_token": access_token},
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        errcode = int(result.get("errcode") or 0)
        if errcode == 0:
            return result
        if errcode in {40001, 42001} and attempt == 0:
            logger.info("WeChat access token expired while deleting menu, retrying once.")
            continue
        raise RuntimeError(f"Failed to delete WeChat menu: {result}")

    raise RuntimeError("Failed to delete WeChat menu")


def sync_wechat_menu() -> dict:
    payload = build_wechat_menu_payload()

    for attempt in range(2):
        access_token = get_wechat_access_token(force_refresh=attempt > 0)
        response = requests.post(
            "https://api.weixin.qq.com/cgi-bin/menu/create",
            params={"access_token": access_token},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        errcode = int(result.get("errcode") or 0)
        if errcode == 0:
            return {"menu": payload, "wechat_result": result}
        if errcode in {40001, 42001} and attempt == 0:
            logger.info("WeChat access token expired while syncing menu, retrying once.")
            continue
        raise RuntimeError(f"Failed to sync WeChat menu: {result}")

    raise RuntimeError("Failed to sync WeChat menu")


def reset_wechat_menu() -> dict:
    delete_result = delete_wechat_menu()
    sync_result = sync_wechat_menu()
    return {
        "delete_result": delete_result,
        **sync_result,
    }


def build_wechat_text_reply(
    to_user: str,
    from_user: str,
    content: str,
) -> str:
    timestamp = int(datetime.now().timestamp())
    safe_content = str(content or "").replace("<![CDATA[", "").replace("]]>", "")
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{timestamp}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{safe_content}]]></Content>"
        "</xml>"
    )


def notify_supplier_onboarding_result(
    db: Session,
    supplier: Supplier,
    review_status: str,
    review_comment: Optional[str] = None,
) -> dict[str, object]:
    template_id = str(settings.WECHAT_TEMPLATE_ONBOARDING_RESULT_ID or "").strip()
    if not template_id:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_template_id"}

    openids = collect_supplier_openids(db, supplier, include_pending=True)
    if not openids:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_openid"}

    status_map = {
        "approved": "审核通过",
        "pending": "审核退回",
        "rejected": "审核未通过",
    }
    status_text = status_map.get(str(review_status or "").strip().lower(), review_status or "待处理")
    data = {
        "thing8": _wrap_template_value(supplier.name or "-"),
        "const3": _wrap_template_value(status_text),
        "thing4": _wrap_template_value(_get_supplier_account_label(db, supplier)),
    }
    return _batch_send_template_message(
        openids,
        template_id,
        data,
        url=_build_supplier_portal_url("/supplier/onboard"),
    )


def notify_new_inquiry_invitation(
    db: Session,
    task: InquiryTask,
    supplier: Supplier,
) -> dict[str, object]:
    template_id = str(settings.WECHAT_TEMPLATE_NEW_INQUIRY_ID or "").strip()
    if not template_id:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_template_id"}

    openids = collect_supplier_openids(db, supplier, include_pending=False)
    if not openids:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_openid"}

    data = {
        "thing3": _wrap_template_value(_get_task_buyer_unit_label(task)),
        "thing8": _wrap_template_value(supplier.name or "-"),
        "time30": _wrap_template_value(_format_dt(task.deadline)),
    }
    return _batch_send_template_message(
        openids,
        template_id,
        data,
        url=_build_supplier_inquiry_url(db, task, supplier, action="detail"),
    )


def notify_warning_message(
    db: Session,
    supplier: Supplier,
    required_delivery_time: object,
    anomaly_time: object,
    project_name: Optional[str] = None,
    buyer_name: Optional[str] = None,
) -> dict[str, object]:
    template_id = str(settings.WECHAT_TEMPLATE_WARNING_ID or "").strip()
    if not template_id:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_template_id"}

    openids = collect_supplier_openids(db, supplier, include_pending=False)
    if not openids:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_openid"}

    data = {
        "time4": _wrap_template_value(_format_dt(required_delivery_time)),
        "thing6": _wrap_template_value(supplier.name or "-"),
        "time13": _wrap_template_value(_format_dt(anomaly_time)),
        "thing9": _wrap_template_value(project_name or buyer_name or "-"),
    }
    return _batch_send_template_message(
        openids,
        template_id,
        data,
        url=_build_supplier_portal_url("/supplier/warnings"),
    )


def notify_inquiry_result(
    db: Session,
    task: InquiryTask,
    supplier: Supplier,
    result_text: str,
    remark: Optional[str] = None,
) -> dict[str, object]:
    template_id = str(settings.WECHAT_TEMPLATE_INQUIRY_RESULT_ID or "").strip()
    if not template_id:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_template_id"}

    openids = collect_supplier_openids(db, supplier, include_pending=False)
    if not openids:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_openid"}

    inquiry_no = f"INQ-{task.id:06d}"
    data = {
        "thing2": _wrap_template_value(task.title or "-"),
        "const3": _wrap_template_value(result_text or "-"),
        "thing4": _wrap_template_value(_get_awarded_supplier_label(task)),
        "thing9": _wrap_template_value(_get_task_material_label(task)),
        "character_string1": _wrap_template_value(inquiry_no),
    }
    return _batch_send_template_message(
        openids,
        template_id,
        data,
        url=_build_supplier_inquiry_url(db, task, supplier, action="detail"),
    )


def notify_quote_deadline_reminder(
    db: Session,
    task: InquiryTask,
    supplier: Supplier,
) -> dict[str, object]:
    template_id = str(settings.WECHAT_TEMPLATE_QUOTE_DEADLINE_REMINDER_ID or "").strip()
    if not template_id:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_template_id"}

    openids = collect_supplier_openids(db, supplier, include_pending=False)
    if not openids:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_openid"}

    data = {
        "thing12": _wrap_template_value(task.title or _get_task_project_label(task)),
        "time15": _wrap_template_value(_format_dt(task.deadline)),
    }
    return _batch_send_template_message(
        openids,
        template_id,
        data,
        url=_build_supplier_inquiry_url(db, task, supplier, action="detail"),
    )


def dispatch_quote_deadline_reminders(db: Session) -> dict[str, int]:
    template_id = str(settings.WECHAT_TEMPLATE_QUOTE_DEADLINE_REMINDER_ID or "").strip()
    if not template_id:
        return {"scanned_tasks": 0, "sent_count": 0}

    now = datetime.now()
    candidate_tasks = (
        db.query(InquiryTask)
        .filter(InquiryTask.status.in_([TaskStatus.ACTIVE, TaskStatus.PENDING_FILL]))
        .filter(InquiryTask.deadline.isnot(None))
        .all()
    )

    sent_count = 0
    scanned_tasks = 0
    for task in candidate_tasks:
        if not task.deadline:
            continue
        seconds_left = (task.deadline - now).total_seconds()
        if seconds_left > 0 or seconds_left < -(24 * 3600):
            continue

        scanned_tasks += 1
        for link in (task.suppliers or []):
            if link.status not in [LinkStatus.SENT, LinkStatus.NEGOTIATION]:
                continue
            supplier = getattr(link, "supplier", None)
            if not supplier:
                continue

            cache_key = (
                f"{WECHAT_DEADLINE_REMINDER_CACHE_PREFIX}:"
                f"{task.id}:{supplier.id}:{int(task.deadline.timestamp())}"
            )
            if cache_get(cache_key):
                continue

            result = notify_quote_deadline_reminder(db, task, supplier)
            if int(result.get("sent_count") or 0) > 0:
                sent_count += int(result.get("sent_count") or 0)
                ttl = max(int(seconds_left) + 3600, 3600)
                cache_set(cache_key, {"sent": True}, ttl=ttl)

    return {"scanned_tasks": scanned_tasks, "sent_count": sent_count}


def notify_contract_confirm(
    db: Session,
    task: InquiryTask,
    supplier: Supplier,
    contract_no: str,
    status_text: str = "待确认",
    remark: Optional[str] = None,
) -> dict[str, object]:
    template_id = str(settings.WECHAT_TEMPLATE_CONTRACT_CONFIRM_ID or "").strip()
    if not template_id:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_template_id"}

    openids = collect_supplier_openids(db, supplier, include_pending=False)
    if not openids:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_openid"}

    data = {
        "thing1": _wrap_template_value(task.title or "-"),
        "character_string2": _wrap_template_value(contract_no or f"CT-{task.id:06d}"),
        "thing11": _wrap_template_value(_get_contract_buyer_label(db, task, supplier)),
    }
    return _batch_send_template_message(
        openids,
        template_id,
        data,
        url=_build_supplier_inquiry_url(db, task, supplier, action="contract"),
    )


def notify_member_review_result(
    user: User,
    supplier_name: str,
    member_name: str,
    review_status: str,
    remark: Optional[str] = None,
) -> dict[str, object]:
    template_id = str(settings.WECHAT_TEMPLATE_MEMBER_REVIEW_ID or "").strip()
    if not template_id:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_template_id"}

    openid = str(getattr(user, "openid", "") or "").strip()
    if not openid:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_openid"}

    review_text = {
        "approved": "审核通过",
        "rejected": "审核未通过",
        "pending": "待补充资料",
    }.get(str(review_status or "").strip().lower(), review_status or "待处理")

    data = {
        "first": _wrap_template_value("供应商成员审核结果已更新，请及时查看。"),
        "keyword1": _wrap_template_value(supplier_name),
        "keyword2": _wrap_template_value(member_name),
        "keyword3": _wrap_template_value(review_text),
        "remark": _wrap_template_value(remark or "请登录系统查看审核详情。"),
    }
    result = send_template_message(
        openid=openid,
        template_id=template_id,
        data=data,
        url=_build_supplier_portal_url("/supplier/members"),
    )
    return {"sent_count": 1, "failed_count": 0, "wechat_result": result}


def send_wechat_test_notification(
    openid: str,
    subject: str,
    result_text: str,
    remark: str,
) -> dict:
    template_id = str(settings.WECHAT_TEMPLATE_ONBOARDING_RESULT_ID or "").strip()
    if not template_id:
        raise RuntimeError("缺少微信测试模板 ID: WECHAT_TEMPLATE_ONBOARDING_RESULT_ID")

    data = {
        "thing8": _wrap_template_value(subject or "系统测试企业"),
        "const3": _wrap_template_value(result_text or "审核通过"),
        "thing4": _wrap_template_value(remark or "supplier_test_account"),
    }
    return send_template_message(
        openid=openid,
        template_id=template_id,
        data=data,
        url=_resolve_template_url(),
    )
