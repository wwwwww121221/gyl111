from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from models import get_db, User, PurchaseOrderHistory, Supplier, Material, InquiryRequest
from routers.auth import get_current_user_auth
from services.llm_factory import get_llm_service
from schemas import ChatMessage
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class CompareRequest(BaseModel):
    material_code: str
    material_name: str
    suppliers: List[Dict[str, Any]]

class HistoryPriceResponse(BaseModel):
    supplier_code: str
    supplier_name: str
    latest_price: float = 0.0
    latest_date: str = ""
    lowest_price: float = 0.0
    lowest_date: str = ""
    highest_price: float = 0.0
    highest_date: str = ""
    avg_30_days: float = 0.0

class MaterialSupplierResponse(BaseModel):
    id: Optional[int] = None
    code: str
    name: str
    count: int
    grade: str


class MaterialSupplierBatchRequest(BaseModel):
    material_codes: List[str]


class MaterialLatestPriceResponse(BaseModel):
    latest_price: Optional[float] = None
    latest_date: Optional[str] = None


def _normalize_material_codes(raw_codes: List[str]) -> List[str]:
    normalized_codes = []
    seen_codes = set()
    for raw_code in raw_codes or []:
        code = str(raw_code or "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        normalized_codes.append(code)
    return normalized_codes


def _get_supplier_grade(supplier: Optional[Supplier]) -> str:
    grade = "一般"
    if supplier:
        if getattr(supplier, "grade", None):
            grade = supplier.grade
        elif getattr(supplier, "level", None) == "core":
            grade = "A级"
        elif getattr(supplier, "level", None) == "normal":
            grade = "一般"
    return grade


def _get_material_name_map(db: Session, material_codes: List[str]) -> Dict[str, str]:
    if not material_codes:
        return {}

    rows = db.query(Material.code, Material.name).filter(Material.code.in_(material_codes)).all()
    result = {
        str(row.code or "").strip(): str(row.name or "").strip()
        for row in rows
        if str(row.code or "").strip() and str(row.name or "").strip()
    }

    missing_codes = [code for code in material_codes if code not in result]
    if missing_codes:
        request_rows = db.query(
            InquiryRequest.material_code,
            InquiryRequest.material_name
        ).filter(
            InquiryRequest.material_code.in_(missing_codes)
        ).order_by(
            InquiryRequest.id.desc()
        ).all()

        for row in request_rows:
            code = str(row.material_code or "").strip()
            name = str(row.material_name or "").strip()
            if code and name and code not in result:
                result[code] = name

    return result


def _build_supplier_map(db: Session, supplier_codes: List[str]) -> Dict[str, Supplier]:
    codes = list({code for code in supplier_codes if code})
    if not codes:
        return {}

    suppliers = db.query(Supplier).filter(Supplier.code.in_(codes)).all()
    return {supplier.code: supplier for supplier in suppliers}


def _append_supplier_recommendation(
    result: Dict[str, List[MaterialSupplierResponse]],
    material_code: str,
    supplier_code: str,
    supplier_name: str,
    count: int,
    supplier_map: Dict[str, Supplier],
    limit: int = 3
) -> None:
    if not material_code or not supplier_code:
        return

    result.setdefault(material_code, [])
    if len(result[material_code]) >= limit:
        return
    if any(item.code == supplier_code for item in result[material_code]):
        return

    supplier = supplier_map.get(supplier_code)
    result[material_code].append(MaterialSupplierResponse(
        id=supplier.id if supplier else None,
        code=supplier_code,
        name=supplier_name,
        count=count,
        grade=_get_supplier_grade(supplier)
    ))

@router.get("/suppliers/{material_code}", response_model=List[MaterialSupplierResponse])
def get_material_suppliers(material_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_auth)):
    """
    获取曾经供应过该物料的历史供应商，按采购次数降序排列
    """
    normalized_code = str(material_code or "").strip()
    if not normalized_code:
        return []

    trimmed_material_code = func.trim(PurchaseOrderHistory.material_code)
    records = db.query(
        PurchaseOrderHistory.supplier_code,
        PurchaseOrderHistory.supplier_name,
        func.count(PurchaseOrderHistory.id).label('count')
    ).filter(
        trimmed_material_code == normalized_code
    ).group_by(
        PurchaseOrderHistory.supplier_code,
        PurchaseOrderHistory.supplier_name
    ).order_by(
        desc('count')
    ).all()
    
    if not records:
        material_name = _get_material_name_map(db, [normalized_code]).get(normalized_code)
        if material_name:
            records = db.query(
                PurchaseOrderHistory.supplier_code,
                PurchaseOrderHistory.supplier_name,
                func.count(PurchaseOrderHistory.id).label('count')
            ).filter(
                func.trim(PurchaseOrderHistory.material_name) == material_name
            ).group_by(
                PurchaseOrderHistory.supplier_code,
                PurchaseOrderHistory.supplier_name
            ).order_by(
                desc('count')
            ).all()

    supplier_map = _build_supplier_map(db, [r.supplier_code for r in records if r.supplier_code])
    result_map: Dict[str, List[MaterialSupplierResponse]] = {normalized_code: []}
    for r in records:
        _append_supplier_recommendation(
            result_map,
            normalized_code,
            r.supplier_code,
            r.supplier_name,
            r.count,
            supplier_map
        )
    return result_map[normalized_code]


@router.post("/suppliers/batch", response_model=Dict[str, List[MaterialSupplierResponse]])
def get_material_suppliers_batch(
    payload: MaterialSupplierBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth)
):
    """
    批量获取多个物料的历史供应商推荐，减少前端在多物料场景下的请求次数。
    """
    normalized_codes = _normalize_material_codes(payload.material_codes)

    if not normalized_codes:
        return {}

    trimmed_material_code = func.trim(PurchaseOrderHistory.material_code)
    records = db.query(
        trimmed_material_code.label("material_code"),
        PurchaseOrderHistory.supplier_code,
        PurchaseOrderHistory.supplier_name,
        func.count(PurchaseOrderHistory.id).label("count")
    ).filter(
        trimmed_material_code.in_(normalized_codes)
    ).group_by(
        trimmed_material_code,
        PurchaseOrderHistory.supplier_code,
        PurchaseOrderHistory.supplier_name
    ).order_by(
        trimmed_material_code,
        desc("count")
    ).all()

    result: Dict[str, List[MaterialSupplierResponse]] = {code: [] for code in normalized_codes}
    supplier_codes = [r.supplier_code for r in records if getattr(r, "supplier_code", None)]
    missing_codes = set(normalized_codes)
    for record in records:
        material_code = str(record.material_code or "").strip()
        if material_code in missing_codes:
            missing_codes.remove(material_code)

    fallback_records = []
    fallback_name_to_codes: Dict[str, List[str]] = {}
    if missing_codes:
        material_name_map = _get_material_name_map(db, list(missing_codes))
        for code, name in material_name_map.items():
            fallback_name_to_codes.setdefault(name, []).append(code)

        if fallback_name_to_codes:
            fallback_records = db.query(
                func.trim(PurchaseOrderHistory.material_name).label("material_name"),
                PurchaseOrderHistory.supplier_code,
                PurchaseOrderHistory.supplier_name,
                func.count(PurchaseOrderHistory.id).label("count")
            ).filter(
                func.trim(PurchaseOrderHistory.material_name).in_(list(fallback_name_to_codes.keys()))
            ).group_by(
                func.trim(PurchaseOrderHistory.material_name),
                PurchaseOrderHistory.supplier_code,
                PurchaseOrderHistory.supplier_name
            ).order_by(
                func.trim(PurchaseOrderHistory.material_name),
                desc("count")
            ).all()
            supplier_codes.extend([
                r.supplier_code for r in fallback_records
                if getattr(r, "supplier_code", None)
            ])

    supplier_map = _build_supplier_map(db, supplier_codes)
    for record in records:
        material_code = str(record.material_code or "").strip()
        supplier_code = record.supplier_code
        _append_supplier_recommendation(
            result,
            material_code,
            supplier_code,
            record.supplier_name,
            record.count,
            supplier_map
        )

    for record in fallback_records:
        material_name = str(record.material_name or "").strip()
        for material_code in fallback_name_to_codes.get(material_name, []):
            _append_supplier_recommendation(
                result,
                material_code,
                record.supplier_code,
                record.supplier_name,
                record.count,
                supplier_map
            )

    return result


@router.post("/latest-prices/batch", response_model=Dict[str, MaterialLatestPriceResponse])
def get_material_latest_prices_batch(
    payload: MaterialSupplierBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth)
):
    """
    批量获取多个物料最近一次成交的不含税单价，供自动询价默认期望单价使用。
    """
    normalized_codes = _normalize_material_codes(payload.material_codes)

    if not normalized_codes:
        return {}

    trimmed_material_code = func.trim(PurchaseOrderHistory.material_code)
    records = db.query(
        trimmed_material_code.label("material_code"),
        PurchaseOrderHistory.price,
        PurchaseOrderHistory.date,
        PurchaseOrderHistory.id
    ).filter(
        trimmed_material_code.in_(normalized_codes),
        PurchaseOrderHistory.price.isnot(None)
    ).order_by(
        trimmed_material_code,
        PurchaseOrderHistory.date.desc(),
        PurchaseOrderHistory.id.desc()
    ).all()

    result: Dict[str, MaterialLatestPriceResponse] = {
        code: MaterialLatestPriceResponse()
        for code in normalized_codes
    }

    for record in records:
        material_code = str(record.material_code or "").strip()
        if not material_code or result.get(material_code, None) is None:
            continue
        if result[material_code].latest_price is not None:
            continue
        result[material_code] = MaterialLatestPriceResponse(
            latest_price=float(record.price) if record.price is not None else None,
            latest_date=record.date.strftime("%Y-%m-%d") if record.date else None
        )

    missing_codes = [
        code for code in normalized_codes
        if result[code].latest_price is None
    ]
    material_name_map = _get_material_name_map(db, missing_codes)
    fallback_name_to_codes: Dict[str, List[str]] = {}
    for code, name in material_name_map.items():
        fallback_name_to_codes.setdefault(name, []).append(code)

    if fallback_name_to_codes:
        fallback_records = db.query(
            func.trim(PurchaseOrderHistory.material_name).label("material_name"),
            PurchaseOrderHistory.price,
            PurchaseOrderHistory.date,
            PurchaseOrderHistory.id
        ).filter(
            func.trim(PurchaseOrderHistory.material_name).in_(list(fallback_name_to_codes.keys())),
            PurchaseOrderHistory.price.isnot(None)
        ).order_by(
            func.trim(PurchaseOrderHistory.material_name),
            PurchaseOrderHistory.date.desc(),
            PurchaseOrderHistory.id.desc()
        ).all()

        for record in fallback_records:
            material_name = str(record.material_name or "").strip()
            for code in fallback_name_to_codes.get(material_name, []):
                if result[code].latest_price is not None:
                    continue
                result[code] = MaterialLatestPriceResponse(
                    latest_price=float(record.price) if record.price is not None else None,
                    latest_date=record.date.strftime("%Y-%m-%d") if record.date else None
                )

    return result

@router.post("/history", response_model=List[HistoryPriceResponse])
def get_history_prices(req: CompareRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_auth)):
    """
    获取选定供应商和物料的历史价格统计 (优化 N+1 查询)
    """
    results = []
    thirty_days_ago = datetime.now() - timedelta(days=30)
    normalized_code = str(req.material_code or "").strip()
    
    supplier_codes = [s.get("code") for s in req.suppliers if s.get("code")]
    if not supplier_codes or not normalized_code:
        return []

    # 一次性查出所有相关供应商在该物料下的所有历史订单
    trimmed_material_code = func.trim(PurchaseOrderHistory.material_code)
    all_records = db.query(PurchaseOrderHistory).filter(
        trimmed_material_code == normalized_code,
        PurchaseOrderHistory.supplier_code.in_(supplier_codes)
    ).all()

    if not all_records:
        normalized_name = str(req.material_name or "").strip()
        if normalized_name:
            all_records = db.query(PurchaseOrderHistory).filter(
                func.trim(PurchaseOrderHistory.material_name) == normalized_name,
                PurchaseOrderHistory.supplier_code.in_(supplier_codes)
            ).all()

    # 按照 supplier_code 分组处理数据
    records_by_supplier = {}
    for r in all_records:
        records_by_supplier.setdefault(r.supplier_code, []).append(r)

    for s in req.suppliers:
        supplier_code = s.get("code")
        supplier_name = s.get("name")
        
        supplier_records = records_by_supplier.get(supplier_code, [])
        
        if not supplier_records:
            results.append(HistoryPriceResponse(
                supplier_code=supplier_code or "",
                supplier_name=supplier_name or ""
            ))
            continue
            
        # 按日期排序获取最近一次
        sorted_by_date = sorted(supplier_records, key=lambda x: x.date or datetime.min, reverse=True)
        latest_record = sorted_by_date[0]
        
        # 按价格排序获取最低和最高
        valid_price_records = [r for r in supplier_records if r.tax_net_price is not None]
        if valid_price_records:
            sorted_by_price = sorted(valid_price_records, key=lambda x: x.tax_net_price)
            lowest_record = sorted_by_price[0]
            highest_record = sorted_by_price[-1]
        else:
            lowest_record = None
            highest_record = None
            
        # 计算近30天均价
        recent_records = [r for r in valid_price_records if r.date and r.date >= thirty_days_ago]
        if recent_records:
            avg_30 = sum(float(r.tax_net_price) for r in recent_records) / len(recent_records)
        else:
            avg_30 = 0.0
        
        results.append(HistoryPriceResponse(
            supplier_code=supplier_code or "",
            supplier_name=supplier_name or "",
            latest_price=float(latest_record.tax_net_price) if latest_record and latest_record.tax_net_price else 0.0,
            latest_date=latest_record.date.strftime("%Y-%m-%d") if latest_record and latest_record.date else "-",
            lowest_price=float(lowest_record.tax_net_price) if lowest_record and lowest_record.tax_net_price else 0.0,
            lowest_date=lowest_record.date.strftime("%Y-%m-%d") if lowest_record and lowest_record.date else "-",
            highest_price=float(highest_record.tax_net_price) if highest_record and highest_record.tax_net_price else 0.0,
            highest_date=highest_record.date.strftime("%Y-%m-%d") if highest_record and highest_record.date else "-",
            avg_30_days=avg_30
        ))
        
    return results

@router.post("/ai-analysis")
async def generate_ai_analysis(req: CompareRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_auth)):
    """
    生成 AI 谈判策略
    """
    history_stats = get_history_prices(req, db, current_user)
    
    supplier_info = {}
    for s in req.suppliers:
        code = s.get("code")
        if code:
            supplier_record = db.query(Supplier).filter(Supplier.code == code).first()
            supplier_info[code] = {
                "grade": supplier_record.grade if supplier_record and supplier_record.grade else "一般"
            }
        else:
            supplier_info[code] = {"grade": "未知"}
            
    input_data = []
    for s, h in zip(req.suppliers, history_stats):
        grade = supplier_info.get(s.get("code"), {}).get("grade", "一般")
        price = s.get("tax_net_price", "未知")
        input_data.append(f"- {s.get('name')}（评级：{grade}，当前报价：{price}元，历史最低价：{h.lowest_price}元）")
        
    input_data_str = "\n".join(input_data)
    
    system_prompt = f"""你是一个资深的供应链采购谈判专家。现在采购员收到了几家供应商关于物料“{req.material_name}”的线下报价，请你基于以下数据生成分析报告与谈判策略。

数据输入：
{input_data_str}

输出要求（严格按照以下4点结构，使用 Markdown 格式）：
- 仅允许使用：标题（###）、有序/无序列表、加粗、换行。
- 允许少量 emoji 作为要点符号（如 ✅ ⚠️ 👉）。
- 不要使用：代码块、表格、长段缩进（避免影响页面排版）。
- 请尽量简短：总字数控制在 300-450 字内；每个小节不超过 2-3 句或 3 个要点；只输出这4个小节，不要追加“注/补充/延伸分析”。
1. 价格差额显著：指出绝对差价。
2. 相对增幅明确：计算百分比差异。
3. 性价比差异突出：结合供应商评级分析性价比。
4. 核心建议与谈判策略：请判断当前最高价、最低价和常用供应商的关系。如果常用供应商价格偏高，必须强烈建议采购员采用“份额切割”策略（例如保留80%给常用，将 20% 的订单切给报最低价的新供应商进行灰度测试），以此作为筹码向常用供应商施压降价。

请额外重点判断并明确写出：
- 当前谁是最高价、谁是最低价、谁是常用供应商（如果信息不足也要说明）。
- 分析最低价与常用供应商是否为同一家，以及最高价与常用供应商之间的关系。
- 如果常用供应商价格偏高，请明确说明为什么应该采用“保留主供份额 + 小比例切单测试”的策略，并给出类似 80% / 20% 的建议比例。
- 如果常用供应商本身就是最低价或综合性价比最优，也要明确说明是否仍建议维持主供份额。"""

    llm = get_llm_service()
    try:
        response = await llm.chat_completion([
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content="请分析并给出谈判策略。")
        ])
        return {"analysis": response.content}
    except Exception as e:
        logger.error(f"AI Analysis failed: {e}")
        return {"analysis": f"AI 分析失败: {str(e)}"}

class WechatScriptRequest(BaseModel):
    material_name: str
    target_supplier: str
    target_price: float
    analysis_text: str

@router.post("/wechat-script")
async def generate_wechat_script(req: WechatScriptRequest, current_user: User = Depends(get_current_user_auth)):
    """
    根据AI策略生成微信沟通话术
    """
    system_prompt = f"""你是一个资深的采购员，深谙人情世故与谈判技巧。
目前你需要给供应商【{req.target_supplier}】发微信，沟通关于物料【{req.material_name}】的价格。
你的目标价格是【{req.target_price}元】。
以下是系统生成的背景策略：
{req.analysis_text}

请根据以上背景，直接生成一段发给该供应商老板的微信文字（字数在150字以内）。
要求：
1. 语气客气但带有商务施压（例如“目前别家给了很有诚意的价格”、“考虑到我们长期合作”）。
2. 直接包含目标价格。
3. 不要出现“系统分析”、“AI建议”等字眼。
4. 不要编造对方姓名或称谓，统一使用“您好/您/贵司负责人”等称呼。
5. 灵活运用“份额分配”作为谈判筹码。例如：明确且客气地告知对方，由于别家价格优势明显，本次系统建议将 20% 的份额划给新渠道测试。但考虑到长期合作信任，如果您愿意将价格降至目标价附近，我们可以手动把 100% 的供货份额都保留给您。"""

    llm = get_llm_service()
    try:
        response = await llm.chat_completion([
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content="请生成微信沟通话术。")
        ])
        return {"script": response.content}
    except Exception as e:
        logger.error(f"Wechat Script failed: {e}")
        return {"script": f"话术生成失败: {str(e)}"}
