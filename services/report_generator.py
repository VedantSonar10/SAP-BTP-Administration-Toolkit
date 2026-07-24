"""
services/report_generator.py

Phase 7 - Report Generator

Bundles authentication status, token info, and endpoint check results
into timestamped JSON, CSV, and TXT reports under reports/.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.logger import logger

REPORTS_DIR = Path("reports")


def _serialize(value: Any) -> Any:
    """Best-effort conversion of dataclasses/datetimes into JSON-safe
    primitives."""
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value


class ReportGenerator:
    """Writes a snapshot of the current session to reports/ in three
    formats."""

    def __init__(self) -> None:
        REPORTS_DIR.mkdir(exist_ok=True)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def generate(
        self,
        auth_status: str,
        token_info: Any | None,
        endpoint_results: list[Any] | None,
    ) -> dict[str, Path]:
        """Write JSON, CSV, and TXT reports and return their paths."""
        timestamp = self._timestamp()
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "authentication_status": auth_status,
            "token_info": _serialize(token_info) if token_info else None,
            "endpoint_results": _serialize(endpoint_results) if endpoint_results else [],
        }

        json_path = REPORTS_DIR / f"report_{timestamp}.json"
        csv_path = REPORTS_DIR / f"report_{timestamp}.csv"
        txt_path = REPORTS_DIR / f"report_{timestamp}.txt"

        self._write_json(json_path, payload)
        self._write_csv(csv_path, payload)
        self._write_txt(txt_path, payload)

        logger.info("Report exported: %s / %s / %s", json_path.name, csv_path.name, txt_path.name)

        return {"json": json_path, "csv": csv_path, "txt": txt_path}

    def _write_json(self, path: Path, payload: dict) -> None:
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _write_csv(self, path: Path, payload: dict) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Generated At", payload["generated_at"]])
            writer.writerow(["Authentication Status", payload["authentication_status"]])
            writer.writerow([])

            writer.writerow(["Endpoint", "Status", "HTTP Code", "Latency (ms)"])
            for result in payload.get("endpoint_results", []) or []:
                writer.writerow(
                    [
                        result.get("name"),
                        result.get("status_label"),
                        result.get("status_code"),
                        result.get("latency_ms"),
                    ]
                )

    def _write_txt(self, path: Path, payload: dict) -> None:
        lines = [
            "=" * 60,
            "SAP BTP ADMINISTRATION TOOLKIT - SESSION REPORT",
            "=" * 60,
            f"Generated At           : {payload['generated_at']}",
            f"Authentication Status  : {payload['authentication_status']}",
            "",
        ]

        if payload.get("token_info"):
            lines.append("Token Information")
            lines.append("-" * 60)
            for key, value in payload["token_info"].items():
                lines.append(f"{key:.<30}{value}")
            lines.append("")

        if payload.get("endpoint_results"):
            lines.append("Endpoint Results")
            lines.append("-" * 60)
            for result in payload["endpoint_results"]:
                lines.append(
                    f"{result.get('name', 'unknown'):.<30}"
                    f"{result.get('status_label', 'N/A')} "
                    f"(HTTP {result.get('status_code', '-')}, "
                    f"{result.get('latency_ms', '-')}ms)"
                )

        lines.append("=" * 60)

        with path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines))
