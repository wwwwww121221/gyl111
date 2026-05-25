from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from collections import defaultdict

from models import (
    get_db, User, Supplier, AssessmentTask, AssessmentItem, AssessmentSupplierScore
)
from routers.inquiry import get_current_user

router = APIRouter()


class AssessmentTaskCreate(BaseModel):
    name: str = Field(..., min_length=1)
    assessment_type: str = Field(..., pattern="^(annual|quarterly|special)$")
    supplier_ids: List[int] = Field(..., min_length=1)
    scoring_start: datetime
    scoring_end: datetime
    description: Optional[str] = None
    scorers: Optional[dict] = None


class ScoreSubmit(BaseModel):
    task_id: int
    supplier_id: int
    item_id: int
    score: float = Field(..., ge=0)
    remark: Optional[str] = None


class BatchScoreSubmit(BaseModel):
    task_id: int
    supplier_id: int
    scores: List[dict]


def _check_scorer_permission(task: AssessmentTask, current_user: User) -> bool:
    if not task.scorers:
        return True
    dept = current_user.department or ""
    allowed_ids = task.scorers.get(dept, [])
    return current_user.id in allowed_ids


@router.get("/items")
def get_assessment_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.query(AssessmentItem).order_by(AssessmentItem.sort_order).all()
    return [
        {
            "id": i.id,
            "dimension": i.dimension,
            "dimension_weight": i.dimension_weight,
            "indicator": i.indicator,
            "max_score": i.max_score,
            "scoring_department": i.scoring_department,
            "sort_order": i.sort_order,
        }
        for i in items
    ]


@router.get("/users-by-department")
def get_users_by_department(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="无权访问")

    departments = db.query(AssessmentItem.scoring_department).distinct().all()
    dept_list = [d[0] for d in departments if d[0]]

    result = {}
    for dept in dept_list:
        users = (
            db.query(User)
            .filter(
                User.department == dept,
                User.role.in_(["admin", "buyer", "buyer_manager"])
            )
            .order_by(User.username)
            .all()
        )
        result[dept] = [
            {"id": u.id, "username": u.username}
            for u in users
        ]
    return result


@router.post("/tasks")
def create_assessment_task(
    payload: AssessmentTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="无权创建考核任务")

    if payload.scoring_end <= payload.scoring_start:
        raise HTTPException(status_code=400, detail="截止时间必须晚于开始时间")

    for sid in payload.supplier_ids:
        supplier = db.query(Supplier).filter(Supplier.id == sid).first()
        if not supplier:
            raise HTTPException(status_code=400, detail=f"供应商ID {sid} 不存在")

    task = AssessmentTask(
        name=payload.name,
        assessment_type=payload.assessment_type,
        scoring_start=payload.scoring_start,
        scoring_end=payload.scoring_end,
        description=payload.description,
        scorers=payload.scorers,
        created_by=current_user.id,
        status="scoring",
    )
    db.add(task)
    db.flush()

    all_items = db.query(AssessmentItem).order_by(AssessmentItem.sort_order).all()
    for sid in payload.supplier_ids:
        for item in all_items:
            score_record = AssessmentSupplierScore(
                task_id=task.id,
                supplier_id=sid,
                item_id=item.id,
            )
            db.add(score_record)

    db.commit()
    db.refresh(task)
    return {"id": task.id, "message": "考核任务创建成功"}


@router.get("/tasks")
def list_assessment_tasks(
    assessment_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AssessmentTask).order_by(AssessmentTask.created_at.desc())

    if assessment_type:
        query = query.filter(AssessmentTask.assessment_type == assessment_type)
    if status_filter:
        query = query.filter(AssessmentTask.status == status_filter)

    tasks = query.all()
    result = []
    for t in tasks:
        supplier_count = (
            db.query(AssessmentSupplierScore.supplier_id)
            .filter(AssessmentSupplierScore.task_id == t.id)
            .distinct()
            .count()
        )
        total_items = db.query(AssessmentSupplierScore).filter(
            AssessmentSupplierScore.task_id == t.id
        ).count()
        scored_items = db.query(AssessmentSupplierScore).filter(
            AssessmentSupplierScore.task_id == t.id,
            AssessmentSupplierScore.score.isnot(None),
        ).count()
        progress = round(scored_items / total_items * 100, 1) if total_items > 0 else 0

        scorers_info = {}
        if t.scorers and isinstance(t.scorers, dict):
            for dept, uids in t.scorers.items():
                scorer_users = db.query(User).filter(User.id.in_(uids)).all()
                scorers_info[dept] = [u.username for u in scorer_users]

        result.append({
            "id": t.id,
            "name": t.name,
            "assessment_type": t.assessment_type,
            "status": t.status,
            "scoring_start": t.scoring_start.strftime("%Y-%m-%d %H:%M:%S") if t.scoring_start else None,
            "scoring_end": t.scoring_end.strftime("%Y-%m-%d %H:%M:%S") if t.scoring_end else None,
            "description": t.description,
            "supplier_count": supplier_count,
            "progress": progress,
            "scorers": scorers_info,
            "created_by": t.creator.username if t.creator else None,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else None,
            "completed_at": t.completed_at.strftime("%Y-%m-%d %H:%M:%S") if t.completed_at else None,
        })
    return result


@router.get("/tasks/{task_id}")
def get_assessment_task_detail(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(AssessmentTask).filter(AssessmentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="考核任务不存在")

    supplier_ids = (
        db.query(AssessmentSupplierScore.supplier_id)
        .filter(AssessmentSupplierScore.task_id == task_id)
        .distinct()
        .all()
    )
    supplier_ids = [s[0] for s in supplier_ids]

    suppliers = db.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all()
    supplier_map = {s.id: s for s in suppliers}

    all_items = db.query(AssessmentItem).order_by(AssessmentItem.sort_order).all()
    item_map = {i.id: i for i in all_items}

    all_scores = db.query(AssessmentSupplierScore).filter(
        AssessmentSupplierScore.task_id == task_id
    ).all()

    supplier_data = []
    for sid in supplier_ids:
        s = supplier_map.get(sid)
        if not s:
            continue
        scores_for_supplier = [sc for sc in all_scores if sc.supplier_id == sid]

        dimension_scores = defaultdict(lambda: {"earned": 0, "max": 0, "items": []})
        for sc in scores_for_supplier:
            item = item_map.get(sc.item_id)
            if not item:
                continue
            dim = item.dimension
            dimension_scores[dim]["earned"] += (sc.score or 0)
            dimension_scores[dim]["max"] += item.max_score
            dimension_scores[dim]["items"].append({
                "item_id": item.id,
                "indicator": item.indicator,
                "max_score": item.max_score,
                "score": sc.score,
                "remark": sc.remark,
                "scored_by": sc.scorer.username if sc.scorer else None,
                "scored_at": sc.scored_at.strftime("%Y-%m-%d %H:%M:%S") if sc.scored_at else None,
            })

        total_score = 0
        dimensions = []
        for item in all_items:
            dim_name = item.dimension
            if dim_name not in [d["dimension"] for d in dimensions]:
                dim_data = dimension_scores.get(dim_name, {"earned": 0, "max": 0, "items": []})
                weight = item.dimension_weight
                earned = dim_data["earned"]
                max_s = dim_data["max"]
                weighted = round(earned / max_s * weight * 100, 2) if max_s > 0 else 0
                total_score += weighted
                dimensions.append({
                    "dimension": dim_name,
                    "weight": weight,
                    "earned": earned,
                    "max": max_s,
                    "weighted_score": weighted,
                    "items": dim_data["items"],
                })

        grade = "一般"
        if total_score >= 90:
            grade = "A级"
        elif total_score >= 75:
            grade = "B级"
        elif total_score >= 60:
            grade = "C级"

        supplier_data.append({
            "supplier_id": s.id,
            "supplier_name": s.name,
            "supplier_code": s.code,
            "total_score": round(total_score, 2),
            "grade": grade,
            "dimensions": dimensions,
        })

    supplier_data.sort(key=lambda x: x["total_score"], reverse=True)

    scorers_info = {}
    if task.scorers and isinstance(task.scorers, dict):
        for dept, uids in task.scorers.items():
            scorer_users = db.query(User).filter(User.id.in_(uids)).all()
            scorers_info[dept] = [{"id": u.id, "username": u.username} for u in scorer_users]

    return {
        "id": task.id,
        "name": task.name,
        "assessment_type": task.assessment_type,
        "status": task.status,
        "scoring_start": task.scoring_start.strftime("%Y-%m-%d %H:%M:%S") if task.scoring_start else None,
        "scoring_end": task.scoring_end.strftime("%Y-%m-%d %H:%M:%S") if task.scoring_end else None,
        "description": task.description,
        "scorers": scorers_info,
        "created_by": task.creator.username if task.creator else None,
        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
        "completed_at": task.completed_at.strftime("%Y-%m-%d %H:%M:%S") if task.completed_at else None,
        "suppliers": supplier_data,
    }


@router.post("/tasks/{task_id}/complete")
def complete_assessment_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="无权完成考核任务")

    task = db.query(AssessmentTask).filter(AssessmentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="考核任务不存在")

    unscored = db.query(AssessmentSupplierScore).filter(
        AssessmentSupplierScore.task_id == task_id,
        AssessmentSupplierScore.score.is_(None),
    ).count()
    if unscored > 0:
        raise HTTPException(status_code=400, detail=f"还有 {unscored} 项未打分，请先完成所有打分")

    all_items = db.query(AssessmentItem).order_by(AssessmentItem.sort_order).all()
    item_map = {i.id: i for i in all_items}

    all_scores = db.query(AssessmentSupplierScore).filter(
        AssessmentSupplierScore.task_id == task_id
    ).all()

    supplier_ids = set(sc.supplier_id for sc in all_scores)

    for sid in supplier_ids:
        scores_for_supplier = [sc for sc in all_scores if sc.supplier_id == sid]
        dimension_earned = defaultdict(float)
        dimension_max = defaultdict(float)
        for sc in scores_for_supplier:
            item = item_map.get(sc.item_id)
            if not item:
                continue
            dimension_earned[item.dimension] += (sc.score or 0)
            dimension_max[item.dimension] += item.max_score

        total_score = 0
        for item in all_items:
            dim = item.dimension
            if dim in dimension_earned:
                earned = dimension_earned[dim]
                max_s = dimension_max[dim]
                total_score += (earned / max_s * item.dimension_weight * 100) if max_s > 0 else 0

        grade = "一般"
        if total_score >= 90:
            grade = "A级"
        elif total_score >= 75:
            grade = "B级"
        elif total_score >= 60:
            grade = "C级"

        supplier = db.query(Supplier).filter(Supplier.id == sid).first()
        if supplier:
            supplier.grade = grade
            supplier.rating_score = round(total_score, 2)

    task.status = "completed"
    task.completed_at = datetime.now()
    db.commit()
    return {"message": "考核任务已完成，供应商等级已更新"}


@router.get("/my-scoring-tasks")
def get_my_scoring_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now()
    active_tasks = db.query(AssessmentTask).filter(
        AssessmentTask.status == "scoring",
        AssessmentTask.scoring_start <= now,
        AssessmentTask.scoring_end >= now,
    ).all()

    result = []
    for task in active_tasks:
        if not _check_scorer_permission(task, current_user):
            continue

        department = current_user.department or ""
        items_for_dept = db.query(AssessmentItem).filter(
            AssessmentItem.scoring_department == department
        ).all()
        if not items_for_dept:
            continue

        item_ids = [i.id for i in items_for_dept]
        total_for_dept = db.query(AssessmentSupplierScore).filter(
            AssessmentSupplierScore.task_id == task.id,
            AssessmentSupplierScore.item_id.in_(item_ids),
        ).count()
        scored_for_dept = db.query(AssessmentSupplierScore).filter(
            AssessmentSupplierScore.task_id == task.id,
            AssessmentSupplierScore.item_id.in_(item_ids),
            AssessmentSupplierScore.score.isnot(None),
        ).count()
        progress = round(scored_for_dept / total_for_dept * 100, 1) if total_for_dept > 0 else 0

        result.append({
            "task_id": task.id,
            "task_name": task.name,
            "assessment_type": task.assessment_type,
            "scoring_start": task.scoring_start.strftime("%Y-%m-%d %H:%M:%S") if task.scoring_start else None,
            "scoring_end": task.scoring_end.strftime("%Y-%m-%d %H:%M:%S") if task.scoring_end else None,
            "progress": progress,
            "total_items": total_for_dept,
            "scored_items": scored_for_dept,
        })
    return result


@router.get("/my-scoring-tasks/{task_id}")
def get_my_scoring_detail(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    department = current_user.department or ""
    task = db.query(AssessmentTask).filter(AssessmentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="考核任务不存在")

    if not _check_scorer_permission(task, current_user):
        raise HTTPException(status_code=403, detail="您未被指定为该考核任务的打分人")

    items_for_dept = db.query(AssessmentItem).filter(
        AssessmentItem.scoring_department == department
    ).order_by(AssessmentItem.sort_order).all()
    if not items_for_dept:
        raise HTTPException(status_code(403), detail="您所在部门无此考核的打分权限")

    item_ids = [i.id for i in items_for_dept]

    scores = db.query(AssessmentSupplierScore).filter(
        AssessmentSupplierScore.task_id == task_id,
        AssessmentSupplierScore.item_id.in_(item_ids),
    ).all()

    supplier_ids = list(set(sc.supplier_id for sc in scores))
    suppliers = db.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all()
    supplier_map = {s.id: s for s in suppliers}

    result = []
    for sid in supplier_ids:
        s = supplier_map.get(sid)
        if not s:
            continue
        supplier_scores = [sc for sc in scores if sc.supplier_id == sid]
        items_detail = []
        for sc in supplier_scores:
            item = next((i for i in items_for_dept if i.id == sc.item_id), None)
            if not item:
                continue
            items_detail.append({
                "score_id": sc.id,
                "item_id": item.id,
                "dimension": item.dimension,
                "indicator": item.indicator,
                "max_score": item.max_score,
                "score": sc.score,
                "remark": sc.remark,
            })
        result.append({
            "supplier_id": s.id,
            "supplier_name": s.name,
            "supplier_code": s.code,
            "items": items_detail,
        })

    return {
        "task_id": task.id,
        "task_name": task.name,
        "assessment_type": task.assessment_type,
        "scoring_start": task.scoring_start.strftime("%Y-%m-%d %H:%M:%S") if task.scoring_start else None,
        "scoring_end": task.scoring_end.strftime("%Y-%m-%d %H:%M:%S") if task.scoring_end else None,
        "can_score": task.status == "scoring" and task.scoring_start <= datetime.now() <= task.scoring_end,
        "suppliers": result,
    }


@router.post("/submit-score")
def submit_score(
    payload: ScoreSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(AssessmentTask).filter(AssessmentTask.id == payload.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="考核任务不存在")

    if task.status != "scoring":
        raise HTTPException(status_code=400, detail="考核任务不在打分阶段")

    if not _check_scorer_permission(task, current_user):
        raise HTTPException(status_code=403, detail="您未被指定为该考核任务的打分人")

    now = datetime.now()
    if now < task.scoring_start or now > task.scoring_end:
        raise HTTPException(status_code=400, detail="不在打分时间范围内")

    item = db.query(AssessmentItem).filter(AssessmentItem.id == payload.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="评分项不存在")

    if item.scoring_department != (current_user.department or ""):
        raise HTTPException(status_code=403, detail="您所在部门无权对该项打分")

    if payload.score > item.max_score:
        raise HTTPException(status_code=400, detail=f"打分不能超过该项满分 {item.max_score}")

    score_record = db.query(AssessmentSupplierScore).filter(
        AssessmentSupplierScore.task_id == payload.task_id,
        AssessmentSupplierScore.supplier_id == payload.supplier_id,
        AssessmentSupplierScore.item_id == payload.item_id,
    ).first()

    if not score_record:
        raise HTTPException(status_code=404, detail="评分记录不存在")

    score_record.score = payload.score
    score_record.remark = payload.remark
    score_record.scored_by = current_user.id
    score_record.scored_at = datetime.now()
    db.commit()
    return {"message": "打分成功"}


@router.post("/batch-submit-scores")
def batch_submit_scores(
    payload: BatchScoreSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(AssessmentTask).filter(AssessmentTask.id == payload.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="考核任务不存在")

    if task.status != "scoring":
        raise HTTPException(status_code=400, detail="考核任务不在打分阶段")

    if not _check_scorer_permission(task, current_user):
        raise HTTPException(status_code=403, detail="您未被指定为该考核任务的打分人")

    now = datetime.now()
    if now < task.scoring_start or now > task.scoring_end:
        raise HTTPException(status_code=400, detail="不在打分时间范围内")

    department = current_user.department or ""
    updated = 0
    for s in payload.scores:
        item_id = s.get("item_id")
        score_val = s.get("score")
        remark_val = s.get("remark")

        if item_id is None or score_val is None:
            continue

        item = db.query(AssessmentItem).filter(AssessmentItem.id == item_id).first()
        if not item:
            continue
        if item.scoring_department != department:
            continue
        if score_val > item.max_score:
            continue

        score_record = db.query(AssessmentSupplierScore).filter(
            AssessmentSupplierScore.task_id == payload.task_id,
            AssessmentSupplierScore.supplier_id == payload.supplier_id,
            AssessmentSupplierScore.item_id == item_id,
        ).first()
        if not score_record:
            continue

        score_record.score = score_val
        score_record.remark = remark_val
        score_record.scored_by = current_user.id
        score_record.scored_at = datetime.now()
        updated += 1

    db.commit()
    return {"message": f"批量打分成功，更新 {updated} 项"}


@router.get("/departments")
def get_scoring_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    departments = db.query(AssessmentItem.scoring_department).distinct().all()
    return [d[0] for d in departments if d[0]]


@router.get("/suppliers-for-task")
def get_suppliers_for_task_creation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="无权访问")

    suppliers = db.query(Supplier).filter(Supplier.status == "approved").order_by(Supplier.name).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "grade": s.grade or "一般",
        }
        for s in suppliers
    ]
