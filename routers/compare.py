from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from models import get_db, User, PurchaseOrderHistory, Supplier
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

class WechatScriptRequest(BaseModel):
    material_name: str
    target_supplier: str
    target_price: float
    analysis_text: str

@router.post("/wechat-script")
def generate_wechat_script(req: WechatScriptRequest, current_user: User = Depends(get_current_user_auth)):
    """
    根据AI比价结论、目标供应商和期望压价目标，生成微信沟通话术
    """
    try:
        llm = get_llm_service()
        prompt = f"""
你是一个资深的采购员，深谙人情世故与谈判技巧。
现在你需要通过微信向供应商【{req.target_supplier}】发消息，就物料【{req.material_name}】进行价格谈判。

背景信息与AI比价结论如下：
{req.analysis_text}

你的核心目标是：
将价格压到 【{req.target_price}】 元左右。

要求：
1. 语气要自然、像真人在微信里聊天，不要像机器生成的正式邮件。
2. 灵活运用“拿A压B”的策略，暗示我们有其他低价渠道，但因为长期合作/信任，还是优先考虑他们。
3. 话术不宜过长，分段清晰，可适当使用emoji（如🤝, 🙏, 😅等）。
4. 结尾要留有余地，促使对方尽快回复或申请特批。

请直接输出微信话术：
"""
        messages = [ChatMessage(role="user", content=prompt)]
        script = llm.chat(messages)
        return {"script": script}
    except Exception as e:
        logger.error(f"Failed to generate wechat script: {str(e)}")
        raise HTTPException(status_code=500, detail="生成话术失败")

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
    code: str
    name: str
    count: int
    grade: str

@router.get("/suppliers/{material_code}", response_model=List[MaterialSupplierResponse])
def get_material_suppliers(material_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_auth)):
    """
    获取曾经供应过该物料的历史供应商，按采购次数降序排列
    """
    records = db.query(
        PurchaseOrderHistory.supplier_code,
        PurchaseOrderHistory.supplier_name,
        func.count(PurchaseOrderHistory.id).label('count')
    ).filter(
        PurchaseOrderHistory.material_code == material_code
    ).group_by(
        PurchaseOrderHistory.supplier_code,
        PurchaseOrderHistory.supplier_name
    ).order_by(
        desc('count')
    ).all()
    
    result = []
    supplier_codes = [r.supplier_code for r in records if r.supplier_code]
    if supplier_codes:
        suppliers = db.query(Supplier).filter(Supplier.code.in_(supplier_codes)).all()
        supplier_map = {s.code: s for s in suppliers}
    else:
        supplier_map = {}

    for r in records:
        if not r.supplier_code:
            continue
        
        supplier = supplier_map.get(r.supplier_code)
        
        grade = "一般"
        if supplier:
            if getattr(supplier, 'grade', None):
                grade = supplier.grade
            elif getattr(supplier, 'level', None) == 'core':
                grade = 'A级'
            elif getattr(supplier, 'level', None) == 'normal':
                grade = '一般'
                
        result.append(MaterialSupplierResponse(
            code=r.supplier_code,
            name=r.supplier_name,
            count=r.count,
            grade=grade
        ))
    return result

@router.post("/history", response_model=List[HistoryPriceResponse])
def get_history_prices(req: CompareRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_auth)):
    """
    获取选定供应商和物料的历史价格统计 (优化 N+1 查询)
    """
    results = []
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    supplier_codes = [s.get("code") for s in req.suppliers if s.get("code")]
    if not supplier_codes:
        return []

    # 一次性查出所有相关供应商在该物料下的所有历史订单
    all_records = db.query(PurchaseOrderHistory).filter(
        PurchaseOrderHistory.material_code == req.material_code,
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
1. 价格差额显著：指出绝对差价。
2. 相对增幅明确：计算百分比差异。
3. 性价比差异突出：结合供应商评级分析性价比。
4. 核心建议与谈判策略：必须包含压价话术建议（如用低评级的低价去压核心供应商的价格）。"""

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
4. 称呼对方为“王总/李总”等通用称呼。"""

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
