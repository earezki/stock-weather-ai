from __future__ import annotations

import os
import re
import json
from pathlib import Path
from datetime import datetime, date
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


app = FastAPI(title="Stock Weather AI Reports API", version="0.1.0")

# Allow CORS for local frontend dev servers (Vite). Adjust origins for production.
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
