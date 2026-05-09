from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Any
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import asyncio

from models import (
    get_db, SessionLocal, InquirySupplier, InquiryTaskItem,
    Quotation, LinkStatus, InquiryRequest, TaskStatus, InquiryTask, Supplier, User, Contract, SupplierMetric, PurchaseOrderHistory
)
from schemas_supplier import QuoteSubmission, SupplierQuoteResponse, SupplierUpdate, SupplierContractInfoSubmit
from services.contract_service import generate_contract_pdf
from services.negotiation_service import calculate_bargain_feedback, calculate_supplier_scores
import logging
from routers.inquiry import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _generate_contract_pdf_background(inquiry_id: int) -> None:
    db = SessionLocal()
    try:
        asyncio.run(generate_contract_pdf(db, inquiry_id))
    except Exception:
        logger.exception("合同生成失败, inquiry_id=%s", inquiry_id)
        try:
            contract_record = db.query(Contract).filter(Contract.inquiry_supplier_id == inquiry_id).first()
            if contract_record:
                contract_record.status = "failed"
                db.add(contract_record)
                db.commit()
        except Exception:
            logger.exception("更新合同失败状态失败, inquiry_id=%s", inquiry_id)
    finally:
        db.close()

@router.get("/{supplier_id}/analysis")
def get_supplier_analysis(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    采购员获取单个供应商的综合数据画像 (基于真实ERP历史采购订单)
    """
    if current_user.role not in ["admin", "buyer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    if not supplier.code:
        # 如果没有ERP编码，无法关联数据
        return {
            "coreStats": {
                "totalAmount": 0.0,
                "orderCount": 0,
                "materialCount": 0,
                "avgTaxNetPrice": 0.0,
                "maxQty": 0,
                "daysSinceLastOrder": 0
            },
            "trend": { "data": [], "topMaterials": [], "allMaterials": [] },
            "radar": [70, 70, 70, 70, 70],
            "tableData": []
        }

    from models import PurchaseOrderHistory
    
    # 获取该供应商的所有历史订单明细
    history_records = db.query(PurchaseOrderHistory).filter(
        PurchaseOrderHistory.supplier_code == supplier.code
    ).order_by(PurchaseOrderHistory.date.desc()).all()
    
    if not history_records:
        return {
            "coreStats": {
                "totalAmount": 0.0,
                "orderCount": 0,
                "materialCount": 0,
                "avgTaxNetPrice": 0.0,
                "maxQty": 0,
                "daysSinceLastOrder": 0
            },
            "trend": { "data": [], "topMaterials": [], "allMaterials": [] },
            "radar": [70, 70, 70, 70, 70],
            "tableData": []
        }

    # 1. 核心指标统计
    total_amount = sum(r.qty * r.tax_net_price for r in history_records if r.qty and r.tax_net_price)
    order_count = len(set(r.bill_no for r in history_records))
    material_count = len(set(r.material_code for r in history_records))
    
    # 平均含税单价 (简单平均)
    valid_prices = [r.tax_net_price for r in history_records if r.tax_net_price and r.tax_net_price > 0]
    avg_tax_net_price = sum(valid_prices) / len(valid_prices) if valid_prices else 0.0
    
    # 最大单笔采购量
    max_qty = max((r.qty for r in history_records if r.qty), default=0)
    
    # 最近交易距今(天)
    latest_record = history_records[0] # 因为已经按 date.desc() 排序
    days_since_last_order = (datetime.now() - latest_record.date).days if latest_record.date else 0

    # 2. 过去6个月的成交趋势（折线图/散点图：按物料分类）
    six_months_ago = datetime.now() - relativedelta(months=6)
    recent_records = [r for r in history_records if r.date and r.date >= six_months_ago]
    
    from collections import defaultdict
    material_order_counts = defaultdict(int)
    for r in history_records:
        if r.material_name:
            material_order_counts[r.material_name] += 1
            
    sorted_materials = sorted(material_order_counts.items(), key=lambda x: x[1], reverse=True)
    top_5_materials = [m[0] for m in sorted_materials[:5]]
    all_materials = [m[0] for m in sorted_materials]

    trend_data = []
    for r in recent_records:
        trend_data.append({
            "date": r.date.strftime("%Y-%m-%d"),
            "price": float(r.tax_net_price) if r.tax_net_price else 0.0,
            "material": r.material_name or "未知物料",
            "bill_no": r.bill_no
        })

    # 3. 交易明细 (按订单聚合，供前端过滤)
    orders_dict = defaultdict(lambda: {"date": "", "bill_no": "", "total_amount": 0.0, "items": []})
    for r in history_records:
        date_str = r.date.strftime("%Y-%m-%d") if r.date else ""
        key = (date_str, r.bill_no)
        if not orders_dict[key]["bill_no"]:
            orders_dict[key]["date"] = key[0]
            orders_dict[key]["bill_no"] = key[1]
        
        amount = (r.qty or 0) * (r.tax_net_price or 0)
        orders_dict[key]["total_amount"] += amount
        orders_dict[key]["items"].append({
            "material": r.material_name,
            "quantity": float(r.qty) if r.qty else 0,
            "price": float(r.price) if r.price else 0.0,
            "taxNetPrice": float(r.tax_net_price) if r.tax_net_price else 0.0
        })
        
    table_data = list(orders_dict.values())
    table_data.sort(key=lambda x: x["date"], reverse=True)

    # 雷达图 (暂时保持随机，后续可以根据预警数据做真实评价)
    base_score = 80
    radar_scores = [
        min(100, max(60, round(base_score + (hash(supplier.name + "price") % 15 - 5)))),
        min(100, max(60, round(base_score + (hash(supplier.name + "speed") % 15 - 5)))),
        min(100, max(60, round(base_score + (hash(supplier.name + "delivery") % 15 - 5)))),
        min(100, max(60, round(base_score + (hash(supplier.name + "quality") % 15 - 5)))),
        min(100, max(60, round(base_score + (hash(supplier.name + "service") % 15 - 5))))
    ]

    return {
        "coreStats": {
            "totalAmount": round(total_amount, 2),
            "orderCount": order_count,
            "materialCount": material_count,
            "avgTaxNetPrice": round(avg_tax_net_price, 2),
            "maxQty": round(max_qty, 2),
            "daysSinceLastOrder": days_since_last_order
        },
        "trend": {
            "data": trend_data,
            "topMaterials": top_5_materials,
            "allMaterials": all_materials
        },
        "radar": radar_scores,
        "tableData": table_data
    }

@router.get("/list")
def get_supplier_list(db: Session = Depends(get_db)):
    """
    采购员获取所有供应商列表（用于选择派发询价及供应商管理）
    """
    # 按照历史交易次数降序排列，等级辅助排序
    suppliers_with_count = db.query(
        Supplier, 
        func.count(PurchaseOrderHistory.id).label('transaction_count')
    ).outerjoin(
        PurchaseOrderHistory, Supplier.code == PurchaseOrderHistory.supplier_code
    ).group_by(Supplier.id).all()
    
    def sort_key(item):
        supplier, count = item
        grade = "一般"
        if getattr(supplier, 'grade', None):
            grade = supplier.grade
        elif getattr(supplier, 'level', None) == 'core':
            grade = 'A级'
            
        # 交易次数降序，然后是等级升序 (A 优先于 B 优先于 Z)
        return (-count, grade)
    
    sorted_items = sorted(suppliers_with_count, key=sort_key)
    
    result = []
    for s, count in sorted_items:
        grade = "一般"
        if getattr(s, 'grade', None):
            grade = s.grade
        elif getattr(s, 'level', None) == 'core':
            grade = 'A级'
            
        result.append({
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "short_name": s.short_name,
            "grade": grade,
            "contact_person": s.contact_person,
            "phone": s.phone,
            "email": s.email,
            "level": s.level,
            "status": s.status,
            "rating_score": s.rating_score,
            "reviewer_id": s.reviewer_id,
            "reviewed_at": s.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if s.reviewed_at else None,
            "reviewer_name": s.reviewer.username if s.reviewer else None,
            "transaction_count": count
        })
    return result

@router.put("/{supplier_id}")
def update_supplier(
    supplier_id: int, 
    supplier_update: SupplierUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    采购员审核/定级供应商
    """
    if current_user.role not in ["admin", "buyer"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    if supplier_update.status:
        supplier.status = supplier_update.status
        if supplier_update.status in ["approved", "rejected"]:
            supplier.reviewer_id = current_user.id
            supplier.reviewed_at = datetime.now()
    if supplier_update.level:
        supplier.level = supplier_update.level
        
    db.commit()
    db.refresh(supplier)
    
    from routers.system import log_operation
    log_operation(db, current_user.id, "UPDATE_SUPPLIER", f"更新供应商 {supplier.name} 状态为 {supplier.status}, 等级为 {supplier.level}")
    
    return {"message": "Supplier updated successfully", "id": supplier.id, "status": supplier.status, "level": supplier.level}

@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除供应商（仅超级管理员可操作）
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有超级管理员可以删除供应商")
        
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
        
    try:
        from models import WarningMessage, Quotation, Contract
        
        # 1. 删除关联的预警消息
        db.query(WarningMessage).filter(WarningMessage.supplier_id == supplier.id).delete()
        
        # 2. 删除询价关联及子记录
        inquiry_links = db.query(InquirySupplier).filter(InquirySupplier.supplier_id == supplier.id).all()
        for link in inquiry_links:
            db.query(Quotation).filter(Quotation.inquiry_supplier_id == link.id).delete()
            db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).delete()
            db.delete(link)
            
        user_id_to_delete = supplier.user_id
        supplier_name = supplier.name
        
        # 3. 删除供应商主表记录
        db.delete(supplier)
        
        # 4. 如果有绑定的 User 账号，一并删除
        if user_id_to_delete:
            user_account = db.query(User).filter(User.id == user_id_to_delete).first()
            if user_account:
                db.delete(user_account)
                
        # 5. 记录日志
        from routers.system import log_operation
        log_operation(db, current_user.id, "DELETE_SUPPLIER", f"删除了供应商及其关联账号和数据: {supplier_name}")
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除供应商失败: {str(e)}")
        
    return {"message": "供应商已成功删除"}

@router.get("/my-inquiries")
def get_my_inquiries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    供应商登录后获取自己的询价任务列表
    """
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
        
    inquiries = db.query(InquirySupplier).filter(
        InquirySupplier.supplier_id == supplier.id
    ).order_by(InquirySupplier.id.desc()).all()
    
    result = []
    for link in inquiries:
        task = db.query(InquiryTask).filter(InquiryTask.id == link.task_id).first()
        if not task:
            continue
        contract_record = db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).first()
        contract_pdf_path = contract_record.pdf_path if contract_record else None
        contract_status = contract_record.status if contract_record else None
        contract_no = f"HT-{task.id}-{link.id}" if contract_record else None
            
        result.append({
            "inquiry_supplier_id": link.id,
            "task_id": task.id,
            "task_title": task.title,
            "status": link.status,
            "task_status": task.status,
            "current_round": link.current_round,
            "contract_pdf": contract_pdf_path,
            "contract_pdf_path": contract_pdf_path,
            "contract_status": contract_status,
            "contract_no": contract_no,
            "created_at": link.created_at
        })
        
    return result

@router.get("/me")
def get_my_supplier_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    获取当前登录供应商的基础信息（用于前端展示公司名称）
    """
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")

    supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")

    return {
        "id": supplier.id,
        "company_name": supplier.name,
        "contact_person": supplier.contact_person,
        "phone": supplier.phone,
        "email": supplier.email,
        "status": supplier.status,
    }

@router.get("/inquiry/{inquiry_supplier_id}")
def get_inquiry_details(
    inquiry_supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    供应商获取特定询价单的明细（用于报价）
    """
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
    
    link = db.query(InquirySupplier).filter(
        InquirySupplier.id == inquiry_supplier_id,
        InquirySupplier.supplier_id == supplier.id
    ).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="Inquiry not found")
        
    task = db.query(InquiryTask).filter(InquiryTask.id == link.task_id).first()
    contract_record = db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).first()
    contract_pdf_path = contract_record.pdf_path if contract_record else None
    contract_no = f"HT-{task.id}-{link.id}" if contract_record else None
    
    last_round_quotes = {}
    preload_round = None
    if link.status == LinkStatus.QUOTED:
        preload_round = link.current_round
    elif link.current_round > 1:
        preload_round = link.current_round - 1

    if preload_round is not None:
        prev_quotes = db.query(Quotation).filter(
            Quotation.inquiry_supplier_id == link.id,
            Quotation.round == preload_round
        ).all()
        for q in prev_quotes:
            last_round_quotes[q.item_id] = q

    items = []
    for item in task.items:
        prev_q = last_round_quotes.get(item.id)
        default_delivery = prev_q.delivery_date if prev_q and prev_q.delivery_date else item.request.delivery_date

        items.append({
            "request_id": item.request_id,
            "material_name": item.request.material_name,
            "material_code": item.request.material_code,
            "qty": item.request.qty,
            "target_delivery_date": item.request.delivery_date,
            "delivery_date": default_delivery,
            "price": float(prev_q.price) if prev_q and prev_q.price is not None else None,
            "remark": prev_q.remark if prev_q else "",
            "project_name": item.request.project_info.get("name") if item.request.project_info else ""
        })
        
    return {
        "task_title": task.title,
        "task_status": task.status,
        "deadline": task.deadline,
        "round": link.current_round,
        "status": link.status,
        "latest_ai_feedback": link.latest_ai_feedback,
        "contract_pdf": contract_pdf_path,
        "contract_pdf_path": contract_pdf_path,
        "contract_no": contract_no,
        "items": items
    }


@router.post("/inquiries/{inquiry_id}/confirm-contract")
def confirm_contract(
    inquiry_id: int,
    payload: SupplierContractInfoSubmit,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")

    supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")

    link = db.query(InquirySupplier).filter(
        InquirySupplier.id == inquiry_id,
        InquirySupplier.supplier_id == supplier.id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    if link.status != LinkStatus.DEAL:
        raise HTTPException(status_code=400, detail="Only deal inquiry can confirm contract")

    contract_record = db.query(Contract).filter(Contract.inquiry_supplier_id == link.id).first()
    if not contract_record:
        contract_record = Contract(
            task_id=link.task_id,
            inquiry_supplier_id=link.id,
            status="pending"
        )
    contract_record.address = payload.address
    contract_record.legal_representative = payload.legal_representative
    contract_record.agent = payload.agent
    contract_record.contact_phone = payload.contact_phone
    contract_record.bank_name = payload.bank_name
    contract_record.bank_account = payload.bank_account
    contract_record.tax_id = payload.tax_id
    contract_record.fax = payload.fax
    contract_record.postal_code = payload.postal_code
    if payload.buyer_company_name:
        contract_record.buyer_company_name = payload.buyer_company_name
    if contract_record.pdf_path:
        history_versions = list(contract_record.history_versions or [])
        history_versions.append({
            "pdf_path": contract_record.pdf_path,
            "generated_at": datetime.now().isoformat(),
            "event": "supplier_resubmitted"
        })
        contract_record.history_versions = history_versions
        contract_record.pdf_path = None
    contract_record.status = "generating"
    db.add(contract_record)
    db.commit()
    db.refresh(contract_record)

    background_tasks.add_task(_generate_contract_pdf_background, link.id)
    return {"message": "合同信息已提交，正在生成合同", "inquiry_id": link.id}

@router.post("/inquiry/{inquiry_supplier_id}/quote", response_model=SupplierQuoteResponse)
async def submit_quote(
    inquiry_supplier_id: int,
    submission: QuoteSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    供应商提交报价
    """
    if current_user.role != "supplier":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
    
    link = db.query(InquirySupplier).filter(
        InquirySupplier.id == inquiry_supplier_id,
        InquirySupplier.supplier_id == supplier.id
    ).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    link_task = db.query(InquiryTask).filter(InquiryTask.id == link.task_id).first()
    if not link_task:
        raise HTTPException(status_code=404, detail="Inquiry task not found")

    if link_task.deadline and datetime.now() > link_task.deadline:
        raise HTTPException(status_code=400, detail="Inquiry deadline has passed. Quotation submission is closed.")
        
    if link.status == LinkStatus.DEAL or link.status == LinkStatus.REJECT:
        raise HTTPException(status_code=400, detail="Inquiry is already closed for you.")

    if link.status == LinkStatus.QUOTED:
        quote_items = db.query(Quotation).filter(
            Quotation.inquiry_supplier_id == link.id,
            Quotation.round == link.current_round
        ).all()
    elif link.status in [LinkStatus.SENT, LinkStatus.NEGOTIATION]:
        # === 新增：异常报价前置预检 ===
        if not getattr(submission, 'force_submit', False):
            anomaly_names = []
            for item in submission.items:
                # 预查期望价
                t_item = db.query(InquiryTaskItem).filter(
                    InquiryTaskItem.task_id == link.task_id,
                    InquiryTaskItem.request_id == item.request_id
                ).first()
                r_item = db.query(InquiryRequest).filter(InquiryRequest.id == t_item.request_id).first() if t_item else None
                
                if r_item and r_item.target_price and r_item.target_price > 0:
                    # 如果报价偏离期望价 50% 以上，记录异常
                    if item.price <= r_item.target_price * 0.5 or item.price >= r_item.target_price * 1.5:
                        anomaly_names.append(r_item.material_name)
            
            # 如果发现异常，拦截提交并返回特定 action 让前端弹窗
            if anomaly_names:
                names_str = ", ".join(anomaly_names[:3]) + (" 等" if len(anomaly_names) > 3 else "")
                return {
                    "message": f"预警：系统检测到【{names_str}】的报价大幅偏离常规预期，请仔细核对是否报错了规格或单位。如确认无误，请在弹窗中强行提交。",
                    "next_action": "confirm_anomaly",
                    "ai_feedback": ""
                }
        # === 预检结束 ===

        quote_items = []
        for item in submission.items:
            task_item = db.query(InquiryTaskItem).filter(
                InquiryTaskItem.task_id == link.task_id,
                InquiryTaskItem.request_id == item.request_id
            ).first()
            
            if task_item:
                quote = Quotation(
                    inquiry_supplier_id=link.id,
                    round=link.current_round,
                    item_id=task_item.id,
                    qty=item.qty,
                    price=item.price,
                    delivery_date=item.delivery_date,
                    remark=item.remark
                )
                db.add(quote)
                quote_items.append(quote)
        
        link.status = LinkStatus.QUOTED
        db.commit() # 先提交报价记录
    else:
        raise HTTPException(status_code=400, detail="Current link status does not allow quoting.")

    # 2. 检查是否所有活跃的供应商都已完成本轮报价
    all_links = db.query(InquirySupplier).filter(InquirySupplier.task_id == link.task_id).all()
    
    # 获取本轮还在参与的供应商 (状态是 SENT, NEGOTIATION 或 QUOTED)
    # 如果有人还是 SENT 或 NEGOTIATION，说明他还没报完
    all_quoted = True
    for l in all_links:
        if l.status in [LinkStatus.SENT, LinkStatus.NEGOTIATION]:
            all_quoted = False
            break
            
    if not all_quoted:
        link.latest_ai_feedback = "已收到您的报价。目前正在等待其他供应商完成本轮报价，待所有供应商报价完成后，系统将统一下发反馈，请耐心等待。"
        db.commit()
        return {
            "message": "报价已收到，等待其他供应商完成。",
            "next_action": "wait",
            "ai_feedback": link.latest_ai_feedback
        }

    # === 新增：统一秒杀检查 ===
    kill_candidates = []
    for l in all_links:
        if l.status != LinkStatus.QUOTED:
            continue
        l_quotes = db.query(Quotation).filter(
            Quotation.inquiry_supplier_id == l.id,
            Quotation.round == l.current_round
        ).all()
        is_kill = True
        has_target = False
        for q in l_quotes:
            t_item = db.query(InquiryTaskItem).filter(InquiryTaskItem.id == q.item_id).first()
            r_item = db.query(InquiryRequest).filter(InquiryRequest.id == t_item.request_id).first() if t_item else None
            target_p = r_item.target_price if r_item else None

            if target_p is None:
                is_kill = False
                break
            has_target = True
            if q.price > target_p or (target_p > 0 and q.price <= target_p * 0.5):
                is_kill = False
                break
        if has_target and is_kill:
            kill_candidates.append(l)

    if kill_candidates:
        today = datetime.now().date()
        score_input = []
        for c_link in kill_candidates:
            c_quotes = db.query(Quotation).filter(
                Quotation.inquiry_supplier_id == c_link.id,
                Quotation.round == c_link.current_round
            ).all()
            s_items = []
            for q in c_quotes:
                d_days = 0.0
                if isinstance(q.delivery_date, (datetime, date)):
                    d_date = q.delivery_date.date() if isinstance(q.delivery_date, datetime) else q.delivery_date
                    d_days = float((d_date - today).days)
                if d_days < 0:
                    d_days = 0.0
                s_items.append({"price": float(q.price or 0), "qty": float(q.qty or 0), "delivery_days": d_days})
            score_input.append({"supplier_id": c_link.id, "items": s_items})

        score_rows = calculate_supplier_scores(score_input)
        best_supplier_id = (
            max(score_rows, key=lambda r: float(r.get("total_score", 0))).get("supplier_id")
            if score_rows
            else kill_candidates[0].id
        )

        best_link = next(l for l in kill_candidates if l.id == best_supplier_id)
        best_link.status = LinkStatus.DEAL
        best_link.latest_ai_feedback = "您的报价已满足期望目标，系统已触发提前成交机制！"
        link_task.status = TaskStatus.CLOSED

        for ol in all_links:
            if ol.id != best_link.id:
                ol.status = LinkStatus.REJECT
                ol.latest_ai_feedback = "有其他供应商报价达到期望目标，本次询价已提前结束。"
        db.commit()
        return {"message": "触发秒杀条件，系统已自动成交！", "next_action": "deal", "ai_feedback": link.latest_ai_feedback}

    # 3. 所有供应商均已报价，统一处理下一轮逻辑或结束
    strategy = link_task.strategy_config or {}
    max_rounds = strategy.get("max_rounds", 3)
    current_round = link.current_round
    if current_round < max_rounds:
        market_quotes = (
            db.query(Quotation)
            .join(InquirySupplier, Quotation.inquiry_supplier_id == InquirySupplier.id)
            .filter(
                InquirySupplier.task_id == link.task_id,
                InquirySupplier.status != LinkStatus.REJECT,
                Quotation.round == current_round
            )
            .all()
        )
        market_min_price_map = {}
        for mq in market_quotes:
            price = float(mq.price or 0)
            if price <= 0:
                continue
            if mq.item_id not in market_min_price_map or price < market_min_price_map[mq.item_id]:
                market_min_price_map[mq.item_id] = price

        def process_link(l):
            # 获取该供应商本轮报价
            l_quotes = db.query(Quotation).filter(Quotation.inquiry_supplier_id == l.id, Quotation.round == current_round).all()
            if not l_quotes:
                return
                
            feedback_lines = []
            
            for q in l_quotes:
                t_item = db.query(InquiryTaskItem).filter(InquiryTaskItem.id == q.item_id).first()
                r_item = db.query(InquiryRequest).filter(InquiryRequest.id == t_item.request_id).first()
                target_price = float(r_item.target_price) if r_item and r_item.target_price is not None else 0.0
                market_min_price = float(market_min_price_map.get(q.item_id, q.price or 0))
                drop_ratio, suggested_price, feedback = calculate_bargain_feedback(
                    target_price=target_price,
                    market_min_price=market_min_price,
                    current_price=float(q.price or 0),
                    current_round=current_round,
                    max_rounds=max_rounds,
                )
                material_name = r_item.material_name if r_item else f"物料#{q.item_id}"
                if feedback:
                    feedback_lines.append(
                        f"{material_name}：当前报价{float(q.price or 0):.4f}元，建议下调{drop_ratio * 100:.2f}%至{suggested_price:.4f}元。"
                    )
                else:
                    feedback_lines.append(
                        f"{material_name}：当前报价{float(q.price or 0):.4f}元，已接近目标区间，可保持或小幅优化。"
                    )

            l.latest_ai_feedback = "系统已完成本轮价格分析，请参考以下建议进行下一轮报价：\n" + "\n".join(feedback_lines)
            l.current_round += 1
            l.status = LinkStatus.NEGOTIATION

        quoted_links = [l for l in all_links if l.status == LinkStatus.QUOTED]
        for l in quoted_links:
            process_link(l)
        db.commit()
        
        return {
            "message": "所有供应商报价已完成，已触发下一轮谈判。",
            "next_action": "re-quote",
            "ai_feedback": link.latest_ai_feedback
        }
        
    else:
        # 达到最大轮数，等待采购员手动定标
        final_feedback = "最终轮报价已结束，系统已生成综合评分与排名，请等待采购员手动审批定标。"
        for l in all_links:
            if l.status == LinkStatus.QUOTED:
                l.latest_ai_feedback = final_feedback
        db.commit()
        return {
            "message": "谈判轮次已达上限，等待采购员审批",
            "next_action": "wait",
            "ai_feedback": final_feedback
        }
