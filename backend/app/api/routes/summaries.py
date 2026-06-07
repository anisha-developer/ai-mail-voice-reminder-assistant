from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.summary import SummaryDetailResponse, SummaryDetailTextResponse, SummaryGenerateResponse, SummaryListItem
from app.services.email_summarization_service import (
    generate_all_summaries,
    get_summary,
    list_summaries,
    list_todays_summaries,
    summary_to_detail,
    summary_to_item,
)

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.post("/generate-all", response_model=SummaryGenerateResponse)
def generate_summaries(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SummaryGenerateResponse:
    return SummaryGenerateResponse(**generate_all_summaries(db, current_user))


@router.get("", response_model=list[SummaryListItem])
def get_summaries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[SummaryListItem]:
    summaries = list_summaries(db, current_user.id, page, limit)
    return [SummaryListItem(**summary_to_item(summary)) for summary in summaries]


@router.get("/today", response_model=list[SummaryListItem])
def get_todays_summaries(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SummaryListItem]:
    summaries = list_todays_summaries(db, current_user)
    return [SummaryListItem(**summary_to_item(summary)) for summary in summaries]


@router.get("/{summary_id}", response_model=SummaryDetailResponse)
def get_summary_detail(summary_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SummaryDetailResponse:
    summary = get_summary(db, current_user.id, summary_id)
    return SummaryDetailResponse(**summary_to_detail(summary))


@router.get("/{summary_id}/detail", response_model=SummaryDetailTextResponse)
def get_detailed_summary(summary_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SummaryDetailTextResponse:
    summary = get_summary(db, current_user.id, summary_id)
    return SummaryDetailTextResponse(summary_id=summary.id, detailed_summary=summary.detailed_summary)
