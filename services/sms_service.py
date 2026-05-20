import base64
import hashlib
import hmac
import os
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException


_SMS_CODE_STORE: dict[str, dict] = {}
_SMS_SEND_COOLDOWN_SECONDS = 60
_SMS_CODE_EXPIRE_MINUTES = 5


@dataclass
class SmsSendResult:
    message: str
    expires_in_seconds: int
    debug_code: Optional[str] = None


def normalize_phone(phone: str | None) -> str:
    return (phone or "").strip()


def _is_valid_mainland_phone(phone: str) -> bool:
    return len(phone) == 11 and phone.isdigit() and phone.startswith("1")


def validate_phone_or_raise(phone: str) -> str:
    normalized = normalize_phone(phone)
    if not _is_valid_mainland_phone(normalized):
        raise HTTPException(status_code=400, detail="请输入有效的11位手机号")
    return normalized


def _build_store_key(phone: str, scene: str) -> str:
    return f"{scene}:{phone}"


def _generate_sms_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _aliyun_percent_encode(value: str) -> str:
    return quote(value, safe="~")


def _aliyun_sign(params: dict[str, str], access_key_secret: str) -> str:
    sorted_items = sorted(params.items(), key=lambda item: item[0])
    canonicalized = "&".join(
        f"{_aliyun_percent_encode(str(key))}={_aliyun_percent_encode(str(value))}"
        for key, value in sorted_items
    )
    string_to_sign = f"GET&%2F&{_aliyun_percent_encode(canonicalized)}"
    digest = hmac.new(
        f"{access_key_secret}&".encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _resolve_template_code(scene: str) -> str:
    template_map = {
        "login": os.getenv("ALIYUN_SMS_TEMPLATE_CODE_LOGIN", "").strip() or "100001",
        "onboarding": os.getenv("ALIYUN_SMS_TEMPLATE_CODE_ONBOARDING", "").strip() or "100003",
        "join": os.getenv("ALIYUN_SMS_TEMPLATE_CODE_JOIN", "").strip() or "100003",
        "reset_password": os.getenv("ALIYUN_SMS_TEMPLATE_CODE_RESET_PASSWORD", "").strip() or "100003",
    }
    return template_map.get(scene, os.getenv("ALIYUN_SMS_TEMPLATE_CODE", "").strip())


def _aliyun_credentials() -> tuple[str, str, str]:
    access_key_id = os.getenv("ALIYUN_SMS_ACCESS_KEY_ID", "").strip()
    access_key_secret = os.getenv("ALIYUN_SMS_ACCESS_KEY_SECRET", "").strip()
    sign_name = os.getenv("ALIYUN_SMS_SIGN_NAME", "").strip() or "速通互联验证码"

    missing_vars = []
    if not access_key_id:
        missing_vars.append("ALIYUN_SMS_ACCESS_KEY_ID")
    if not access_key_secret:
        missing_vars.append("ALIYUN_SMS_ACCESS_KEY_SECRET")
    if not sign_name:
        missing_vars.append("ALIYUN_SMS_SIGN_NAME")
    if missing_vars:
        raise HTTPException(
            status_code=500,
            detail=f"短信配置未完成，缺少: {', '.join(missing_vars)}",
        )
    return access_key_id, access_key_secret, sign_name


def _call_dypnsapi(action: str, action_params: dict[str, str | int | bool]) -> dict:
    access_key_id, access_key_secret, _ = _aliyun_credentials()
    params = {
        "AccessKeyId": access_key_id,
        "Action": action,
        "Format": "JSON",
        "RegionId": "cn-hangzhou",
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": str(uuid.uuid4()),
        "SignatureVersion": "1.0",
        "Timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Version": "2017-05-25",
    }
    for key, value in action_params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            params[key] = "true" if value else "false"
        else:
            params[key] = str(value)

    params["Signature"] = _aliyun_sign(params, access_key_secret)

    try:
        response = httpx.get(
            "https://dypnsapi.aliyuncs.com/",
            params=params,
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"阿里云号码认证服务请求失败: {exc}") from exc

    if str(payload.get("Code") or "").strip() != "OK":
        provider_code = str(payload.get("Code") or "").strip()
        provider_message = str(payload.get("Message") or "短信服务调用失败").strip()
        if provider_code == "biz.FREQUENCY":
            raise HTTPException(
                status_code=429,
                detail="验证码发送过于频繁，请稍后再试",
            )
        raise HTTPException(
            status_code=502,
            detail=f"阿里云号码认证服务失败[{provider_code}]: {provider_message}",
        )

    return payload


def _send_via_aliyun(phone: str, scene: str) -> None:
    _, _, sign_name = _aliyun_credentials()
    template_code = _resolve_template_code(scene)
    if not template_code:
        raise HTTPException(status_code=500, detail="短信配置未完成，缺少: ALIYUN_SMS_TEMPLATE_CODE")

    template_param = '{"code":"##code##","min":"5"}'
    _call_dypnsapi(
        "SendSmsVerifyCode",
        {
            "PhoneNumber": phone,
            "SignName": sign_name,
            "TemplateCode": template_code,
            "TemplateParam": template_param,
            "CodeType": 1,
            "ValidTime": _SMS_CODE_EXPIRE_MINUTES * 60,
            "Interval": _SMS_SEND_COOLDOWN_SECONDS,
            "DuplicatePolicy": 1,
            "ReturnVerifyCode": False,
            "AutoRetry": 1,
        },
    )


def _check_via_aliyun(phone: str, sms_code: str) -> None:
    payload = _call_dypnsapi(
        "CheckSmsVerifyCode",
        {
            "PhoneNumber": phone,
            "VerifyCode": sms_code,
            "CaseAuthPolicy": 1,
        },
    )
    verify_result = str(((payload.get("Model") or {}).get("VerifyResult")) or "").strip().upper()
    if verify_result != "PASS":
        raise HTTPException(status_code=400, detail="验证码错误或已失效")


def send_sms_code(phone: str, scene: str) -> SmsSendResult:
    normalized_phone = validate_phone_or_raise(phone)
    normalized_scene = (scene or "").strip().lower()
    if normalized_scene not in {"login", "onboarding", "join", "reset_password"}:
        raise HTTPException(status_code=400, detail="短信场景不支持")

    now = time.time()
    key = _build_store_key(normalized_phone, normalized_scene)
    existing = _SMS_CODE_STORE.get(key)
    if existing and now - existing["sent_at"] < _SMS_SEND_COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail="验证码发送过于频繁，请稍后再试")

    debug_mode = os.getenv("SMS_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    debug_code = None
    if debug_mode:
        debug_code = _generate_sms_code()
        _SMS_CODE_STORE[key] = {
            "code": debug_code,
            "sent_at": now,
            "expires_at": now + _SMS_CODE_EXPIRE_MINUTES * 60,
        }
    else:
        _send_via_aliyun(normalized_phone, normalized_scene)
        _SMS_CODE_STORE[key] = {
            "code": None,
            "sent_at": now,
            "expires_at": now + _SMS_CODE_EXPIRE_MINUTES * 60,
        }

    return SmsSendResult(
        message="验证码已发送",
        expires_in_seconds=_SMS_CODE_EXPIRE_MINUTES * 60,
        debug_code=debug_code,
    )


def verify_sms_code(phone: str, scene: str, sms_code: str) -> None:
    normalized_phone = validate_phone_or_raise(phone)
    normalized_scene = (scene or "").strip().lower()
    normalized_code = (sms_code or "").strip()
    key = _build_store_key(normalized_phone, normalized_scene)
    record = _SMS_CODE_STORE.get(key)

    if not record:
        raise HTTPException(status_code=400, detail="验证码不存在或已失效")
    if time.time() > float(record["expires_at"]):
        _SMS_CODE_STORE.pop(key, None)
        raise HTTPException(status_code=400, detail="验证码已过期")

    debug_mode = os.getenv("SMS_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    if debug_mode:
        if record["code"] != normalized_code:
            raise HTTPException(status_code=400, detail="验证码错误")
    else:
        _check_via_aliyun(normalized_phone, normalized_code)

    _SMS_CODE_STORE.pop(key, None)


def cleanup_expired_sms_codes() -> None:
    now = time.time()
    expired_keys = [
        key for key, value in _SMS_CODE_STORE.items()
        if now > float(value.get("expires_at") or 0)
    ]
    for key in expired_keys:
        _SMS_CODE_STORE.pop(key, None)
