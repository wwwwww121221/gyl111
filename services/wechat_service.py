from __future__ import annotations

import logging
import json
from datetime import datetime
from typing import Iterable, Optional
from urllib.parse import urlencode, urlparse

import requests
from sqlalchemy.orm import Session

from core.config import settings
from core.redis_client import cache_get, cache_set
from models import InquirySupplier, InquiryTask, LinkStatus, Supplier, SupplierMember, TaskStatus, User

logger = logging.getLogger(__name__)

WECHAT_ACCESS_TOKEN_CACHE_KEY = "wechat:access_token"
WECHAT_TEMPLATE_COLOR = "#173177"
WECHAT_DEADLINE_REMINDER_CACHE_PREFIX = "wechat:deadline-reminder"


def _wrap_template_value(value: object) -> dict[str, str]:
    return {
        "value": "" if value is None else str(value),
        "color": WECHAT_TEMPLATE_COLOR,
    }


def is_wechat_configured() -> bool:
    return bool(settings.WECHAT_APP_ID and settings.WECHAT_APP_SECRET and settings.WECHAT_TOKEN)


def get_wechat_access_token(force_refresh: bool = False) -> str:
    if not is_wechat_configured():
        raise RuntimeError("微信公众号配置未完成")

    if not force_refresh:
        cached = cache_get(WECHAT_ACCESS_TOKEN_CACHE_KEY)
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
        WECHAT_ACCESS_TOKEN_CACHE_KEY,
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
    return str(url or settings.WECHAT_TEMPLATE_DEFAULT_URL or "").strip() or None


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
    params = {"target": normalized_target}
    normalized_openid = str(openid or "").strip()
    if normalized_openid:
        params["openid"] = normalized_openid
    return build_wechat_frontend_route_url("/wechat/bind", params)


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
    login_url = build_wechat_bind_entry_url(target="login")
    register_url = build_wechat_bind_entry_url(target="register")
    homepage_url = build_wechat_frontend_route_url("/login")

    return {
        "button": [
            {
                "type": "view",
                "name": "\u4f9b\u5e94\u5546\u767b\u5f55",
                "url": login_url,
            },
            {
                "type": "view",
                "name": "\u4f9b\u5e94\u5546\u5165\u9a7b",
                "url": register_url,
            },
            {
                "type": "view",
                "name": "\u5e73\u53f0\u9996\u9875",
                "url": homepage_url,
            },
        ]
    }


def build_wechat_subscribe_welcome_message(openid: str | None = None) -> str:
    base_message = str(settings.WECHAT_SUBSCRIBE_WELCOME_MESSAGE or "").strip()
    login_url = build_wechat_bind_entry_url(openid=openid, target="login")
    register_url = build_wechat_bind_entry_url(openid=openid, target="register")

    lines = [base_message] if base_message else ["欢迎关注供应链协同平台。"]
    lines.extend(
        [
            "",
            "请点击以下链接完成账号绑定：",
            f"供应商登录绑定：{login_url}",
            f"供应商入驻绑定：{register_url}",
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
    remark = review_comment or "请登录供应链系统查看详情。"
    data = {
        "first": _wrap_template_value("供应商入驻审核结果如下，请及时查看。"),
        "keyword1": _wrap_template_value(supplier.name),
        "keyword2": _wrap_template_value(status_text),
        "keyword3": _wrap_template_value(datetime.now().strftime("%Y-%m-%d %H:%M")),
        "remark": _wrap_template_value(remark),
    }
    return _batch_send_template_message(openids, template_id, data, url=_resolve_template_url())


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
        "first": _wrap_template_value("您收到一条新的询价邀请，请尽快登录系统报价。"),
        "keyword1": _wrap_template_value(task.title),
        "keyword2": _wrap_template_value(f"INQ-{task.id:06d}"),
        "keyword3": _wrap_template_value(_format_dt(task.deadline)),
        "remark": _wrap_template_value("如您已完成报价，请忽略此提醒。"),
    }
    return _batch_send_template_message(openids, template_id, data, url=_resolve_template_url())


def notify_warning_message(
    db: Session,
    supplier: Supplier,
    latest_delivery: object,
    item_count: int,
    buyer_name: Optional[str] = None,
) -> dict[str, object]:
    template_id = str(settings.WECHAT_TEMPLATE_WARNING_ID or "").strip()
    if not template_id:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_template_id"}

    openids = collect_supplier_openids(db, supplier, include_pending=False)
    if not openids:
        return {"sent_count": 0, "failed_count": 0, "skipped": "missing_openid"}

    remark = "请及时登录系统查看明细并安排处理。"
    if buyer_name:
        remark = f"采购员 {buyer_name} 已发出提醒，请及时处理。"

    data = {
        "first": _wrap_template_value("您有新的发货预警提醒，请尽快处理。"),
        "keyword1": _wrap_template_value(supplier.name),
        "keyword2": _wrap_template_value(item_count),
        "keyword3": _wrap_template_value(_format_dt(latest_delivery)),
        "remark": _wrap_template_value(remark),
    }
    return _batch_send_template_message(openids, template_id, data, url=_resolve_template_url())


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

    data = {
        "first": _wrap_template_value("询价结果已更新，请及时查看。"),
        "keyword1": _wrap_template_value(task.title),
        "keyword2": _wrap_template_value(f"INQ-{task.id:06d}"),
        "keyword3": _wrap_template_value(result_text),
        "remark": _wrap_template_value(remark or "请登录系统查看结果详情。"),
    }
    return _batch_send_template_message(openids, template_id, data, url=_resolve_template_url())


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
        "first": _wrap_template_value("询价报价即将截止，请尽快处理。"),
        "keyword1": _wrap_template_value(task.title),
        "keyword2": _wrap_template_value(f"INQ-{task.id:06d}"),
        "keyword3": _wrap_template_value(_format_dt(task.deadline)),
        "remark": _wrap_template_value("若已完成报价，请忽略本提醒。"),
    }
    return _batch_send_template_message(openids, template_id, data, url=_resolve_template_url())


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
        if seconds_left <= 0 or seconds_left > 24 * 3600:
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
        "first": _wrap_template_value("合同已生成，请尽快进入系统确认。"),
        "keyword1": _wrap_template_value(task.title),
        "keyword2": _wrap_template_value(contract_no or f"CT-{task.id:06d}"),
        "keyword3": _wrap_template_value(status_text),
        "remark": _wrap_template_value(remark or "请登录系统完善并确认合同信息。"),
    }
    return _batch_send_template_message(openids, template_id, data, url=_resolve_template_url())


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
        "first": _wrap_template_value("供应商成员申请审核结果如下。"),
        "keyword1": _wrap_template_value(supplier_name),
        "keyword2": _wrap_template_value(member_name),
        "keyword3": _wrap_template_value(review_text),
        "remark": _wrap_template_value(remark or "请登录系统查看详情。"),
    }
    result = send_template_message(
        openid=openid,
        template_id=template_id,
        data=data,
        url=_resolve_template_url(),
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
        "first": _wrap_template_value("这是一条来自供应链系统的微信测试消息。"),
        "keyword1": _wrap_template_value(subject or "系统测试"),
        "keyword2": _wrap_template_value(result_text or "发送成功"),
        "keyword3": _wrap_template_value(datetime.now().strftime("%Y-%m-%d %H:%M")),
        "remark": _wrap_template_value(remark or "如您收到此消息，说明微信公众号推送链路已打通。"),
    }
    return send_template_message(
        openid=openid,
        template_id=template_id,
        data=data,
        url=_resolve_template_url(),
    )
