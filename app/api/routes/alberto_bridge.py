import hmac

from sqlalchemy import func, select

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.alberto_bridge.service import claim_next_job, complete_job, recover_expired_jobs, reject_job
from app.core.config import Settings, get_settings
from app.db.deps import get_db
from app.models.alberto_job import AlbertoJob
from app.schemas.alberto_bridge import AlbertoJobCompletion, AlbertoJobRead, AlbertoJobSummary

router = APIRouter(prefix="/alberto", tags=["alberto bridge"])


def require_alberto_token(
    authorization: str = Header(default=""), settings: Settings = Depends(get_settings)
) -> None:
    if not settings.alberto_bridge_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Alberto bridge is not configured")
    supplied = authorization.removeprefix("Bearer ")
    if not hmac.compare_digest(supplied, settings.alberto_bridge_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized")


@router.post("/jobs/next", response_model=AlbertoJobRead | None, dependencies=[Depends(require_alberto_token)])
def next_job(
    worker_name: str = Header(default="alberto", alias="X-Alberto-Worker"),
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> AlbertoJob | None:
    return claim_next_job(db, worker_name[:255], settings.alberto_job_lease_minutes, settings.alberto_job_max_attempts)


@router.get("/jobs/summary", response_model=AlbertoJobSummary, dependencies=[Depends(require_alberto_token)])
def jobs_summary(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> AlbertoJobSummary:
    recover_expired_jobs(db, settings.alberto_job_lease_minutes, settings.alberto_job_max_attempts)
    counts = dict(db.execute(select(AlbertoJob.status, func.count()).group_by(AlbertoJob.status)).all())
    return AlbertoJobSummary(**{state.lower(): counts.get(state, 0) for state in ("PENDING", "CLAIMED", "COMPLETED", "REJECTED", "FAILED")})


@router.post("/jobs/{job_id}/complete", response_model=AlbertoJobRead, dependencies=[Depends(require_alberto_token)])
def finish_job(job_id: int, completion: AlbertoJobCompletion, db: Session = Depends(get_db)) -> AlbertoJob:
    job = db.get(AlbertoJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    try:
        if completion.error:
            return reject_job(db, job, completion.error)
        if completion.result is None:
            raise ValueError("A result or error is required")
        return complete_job(db, job, completion.result)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
