from __future__ import annotations

import os
import re
import json
from pathlib import Path
from datetime import datetime, date, timezone, timedelta
from contextlib import asynccontextmanager
import asyncio
import logging
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports"))
DATE_PATTERN = re.compile(r"evaluation_([A-Z0-9]+)_([0-9]{4}-[0-9]{2}-[0-9]{2})\.json$")


class ReportFile(BaseModel):
	filename: str
	ticker: str
	content: Dict[str, Any]


class ReportsResponse(BaseModel):
	date: date
	files: List[ReportFile]
	available_dates: List[date]


SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "1")

logger = logging.getLogger(__name__)

try:
	# local import to avoid import cycles
	from agents.agent import Agent
except Exception:
	Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
	"""
	Lifespan context manager to start/stop the scheduler with the app.
	"""

	if SCHEDULER_ENABLED != "1":
		logger.info("Scheduler disabled")
		yield
		return

	loop = asyncio.get_event_loop()
	task = loop.create_task(_scheduler_loop(app))
	app.state.scheduler_task = task
	logger.info("Scheduler background task started")

	try:
		yield
	finally:
		# SHUTDOWN: cancel the background task
		task = getattr(app.state, "scheduler_task", None)
		if task:
			logger.info("Cancelling scheduler background task")
			task.cancel()
			try:
				await task
			except asyncio.CancelledError:
				logger.info("Scheduler task cancelled")


app = FastAPI(title="Stock Weather AI Reports API", version="0.1.0", lifespan=lifespan)

# Allow CORS for local frontend dev servers.
app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://localhost:5173",
		"http://localhost:5174",
		"http://127.0.0.1:5173",
		"http://127.0.0.1:5174",
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


def _scan_reports() -> Dict[date, List[Path]]:
	"""Scan the REPORTS_DIR and group report files by date.

	Returns a mapping of date -> list of Path objects.
	Ignores files that do not match naming convention.
	"""
	by_date: Dict[date, List[Path]] = {}
	if not REPORTS_DIR.exists() or not REPORTS_DIR.is_dir():
		return by_date
	for p in REPORTS_DIR.glob("*.json"):
		m = DATE_PATTERN.match(p.name)
		if not m:
			continue
		_ticker, date_str = m.groups()
		try:
			d = datetime.strptime(date_str, "%Y-%m-%d").date()
		except ValueError:
			continue
		by_date.setdefault(d, []).append(p)
	return by_date


def _latest_date(dates: List[date]) -> Optional[date]:
	return max(dates) if dates else None


@app.get("/health")
def health() -> Dict[str, str]:
	return {"status": "ok"}


@app.get("/reports", response_model=ReportsResponse)
def get_reports(date_param: Optional[str] = Query(None, alias="date", description="Date in YYYY-MM-DD format")):
	"""Return report JSON contents for a given date, or the latest available if not provided.

	Response includes the list of available dates for client-side navigation.
	"""
	grouped = _scan_reports()
	if not grouped:
		raise HTTPException(status_code=404, detail="No report files found")

	all_dates = sorted(grouped.keys())

	target_date: Optional[date] = None
	if date_param:
		try:
			target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
		except ValueError:
			raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")
		if target_date not in grouped:
			raise HTTPException(status_code=404, detail=f"No reports found for date {target_date}")
	else:
		target_date = _latest_date(all_dates)
		if target_date is None:
			raise HTTPException(status_code=404, detail="No reports available")

	files: List[ReportFile] = []
	for path in sorted(grouped[target_date]):
		m = DATE_PATTERN.match(path.name)
		if not m:
			continue
		ticker, _ = m.groups()
		try:
			with path.open("r", encoding="utf-8") as f:
				content = json.load(f)
		except Exception as e:  # pragma: no cover - defensive
			raise HTTPException(status_code=500, detail=f"Failed to read {path.name}: {e}")
		files.append(ReportFile(filename=path.name, ticker=ticker, content=content))

	return ReportsResponse(date=target_date, files=files, available_dates=all_dates)


async def _seconds_until_next_midnight_utc() -> float:
	"""Return number of seconds from now until the next UTC midnight.

	Uses aware datetimes in UTC to be explicit about timezone handling.
	"""
	now = datetime.now(timezone.utc)
	# tomorrow at 00:00 UTC
	tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
	delta = tomorrow - now
	return delta.total_seconds()


async def _scheduler_loop(app: FastAPI):
	"""
	Background loop that waits until next midnight UTC then runs Agent.act().
	"""
	if Agent is None:
		logger.warning("Agent class not available; scheduler will not run.")
		return

	while True:
		secs = await _seconds_until_next_midnight_utc()
		logger.info(f"Scheduler sleeping for {secs:.1f}s until next midnight UTC")
		try:
			await asyncio.sleep(secs)
		except asyncio.CancelledError:
			logger.info("Scheduler task cancelled during sleep")
			raise

		try:
			logger.info("Scheduler waking up: running Agent.act()")
			agent = Agent()
			await agent.act()
			logger.info("Agent.act() completed")
		except asyncio.CancelledError:
			logger.info("Scheduler task cancelled during agent run")
			raise
		except Exception as e:
			logger.exception(f"Scheduled run failed: {e}")

