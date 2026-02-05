"""Job statistics tracking for scheduler jobs."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class JobRun:
    """Single job run record."""
    started_at: datetime
    finished_at: Optional[datetime] = None
    processed: int = 0
    success: bool = True
    error: Optional[str] = None


@dataclass
class JobStats:
    """Statistics for a scheduled job."""
    job_id: str
    name: str
    last_run: Optional[JobRun] = None
    total_runs: int = 0
    total_processed: int = 0
    last_error: Optional[str] = None


class JobStatsTracker:
    """Tracks job execution statistics."""

    def __init__(self):
        self._stats: dict[str, JobStats] = {}

    def register_job(self, job_id: str, name: str):
        """Register a job for tracking."""
        if job_id not in self._stats:
            self._stats[job_id] = JobStats(job_id=job_id, name=name)

    def start_run(self, job_id: str) -> JobRun:
        """Record start of a job run."""
        if job_id not in self._stats:
            self._stats[job_id] = JobStats(job_id=job_id, name=job_id)

        run = JobRun(started_at=datetime.utcnow())
        self._stats[job_id].last_run = run
        return run

    def finish_run(self, job_id: str, processed: int = 0, error: Optional[str] = None):
        """Record end of a job run."""
        if job_id not in self._stats:
            return

        stats = self._stats[job_id]
        if stats.last_run:
            stats.last_run.finished_at = datetime.utcnow()
            stats.last_run.processed = processed
            stats.last_run.success = error is None
            stats.last_run.error = error

        stats.total_runs += 1
        stats.total_processed += processed
        if error:
            stats.last_error = error

    def get_stats(self, job_id: str) -> Optional[JobStats]:
        """Get stats for a specific job."""
        return self._stats.get(job_id)

    def get_all_stats(self) -> dict[str, JobStats]:
        """Get all job stats."""
        return self._stats.copy()

    def to_dict(self, job_id: str) -> dict:
        """Convert job stats to dict for API."""
        stats = self._stats.get(job_id)
        if not stats:
            return {}

        result = {
            "job_id": stats.job_id,
            "name": stats.name,
            "total_runs": stats.total_runs,
            "total_processed": stats.total_processed,
            "last_error": stats.last_error,
        }

        if stats.last_run:
            result["last_run"] = {
                "started_at": stats.last_run.started_at.isoformat() if stats.last_run.started_at else None,
                "finished_at": stats.last_run.finished_at.isoformat() if stats.last_run.finished_at else None,
                "processed": stats.last_run.processed,
                "success": stats.last_run.success,
                "error": stats.last_run.error,
            }

        return result


# Global tracker instance
job_stats = JobStatsTracker()
