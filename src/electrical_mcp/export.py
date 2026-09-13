"""Data export capabilities for telemetry data."""
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False


class ExportFormat:
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    EXCEL = "excel"


class TelemetryExporter:
    """Export telemetry data in various formats."""

    def __init__(self):
        self._supported_formats = [ExportFormat.JSON, ExportFormat.CSV]
        if HAS_PANDAS:
            self._supported_formats.append(ExportFormat.EXCEL)
        if HAS_PARQUET:
            self._supported_formats.append(ExportFormat.PARQUET)

    @property
    def supported_formats(self) -> list[str]:
        return self._supported_formats.copy()

    def export_json(self, data: list[dict[str, Any]], pretty: bool = False) -> str:
        """Export data as JSON string."""
        indent = 2 if pretty else None
        return json.dumps(data, indent=indent, default=str)

    def export_json_file(self, data: list[dict[str, Any]], filepath: str, pretty: bool = True) -> None:
        """Export data to a JSON file."""
        content = self.export_json(data, pretty)
        Path(filepath).write_text(content, encoding="utf-8")

    def export_csv(self, data: list[dict[str, Any]], flatten_nested: bool = True) -> str:
        """Export data as CSV string."""
        if not data:
            return ""

        # Flatten nested structures if requested
        if flatten_nested:
            data = [self._flatten_dict(d) for d in data]

        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return output.getvalue()

    def export_csv_file(self, data: list[dict[str, Any]], filepath: str, flatten_nested: bool = True) -> None:
        """Export data to a CSV file."""
        content = self.export_csv(data, flatten_nested)
        Path(filepath).write_text(content, encoding="utf-8")

    def export_parquet(self, data: list[dict[str, Any]], filepath: str) -> None:
        """Export data to a Parquet file."""
        if not HAS_PARQUET:
            raise ImportError("pyarrow is required for Parquet export. Install with: pip install voltbridge-mcp[parquet]")

        if not data:
            raise ValueError("No data to export")

        flattened = [self._flatten_dict(d) for d in data]
        table = pa.Table.from_pylist(flattened)
        pq.write_table(table, filepath)

    def export_excel(self, data: list[dict[str, Any]], filepath: str, sheet_name: str = "Telemetry") -> None:
        """Export data to an Excel file."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for Excel export")

        if not data:
            raise ValueError("No data to export")

        flattened = [self._flatten_dict(d) for d in data]
        df = pd.DataFrame(flattened)
        df.to_excel(filepath, index=False, sheet_name=sheet_name)

    def export_readings(self, readings: list[dict[str, Any]], format: str, filepath: str | None = None) -> str | None:
        """Export readings in the specified format."""
        if format not in self._supported_formats:
            raise ValueError(f"Unsupported format: {format}. Supported: {self._supported_formats}")

        if format == ExportFormat.JSON:
            if filepath:
                self.export_json_file(readings, filepath)
                return None
            return self.export_json(readings)
        elif format == ExportFormat.CSV:
            if filepath:
                self.export_csv_file(readings, filepath)
                return None
            return self.export_csv(readings)
        elif format == ExportFormat.PARQUET:
            if not filepath:
                raise ValueError("filepath is required for Parquet export")
            self.export_parquet(readings, filepath)
            return None
        elif format == ExportFormat.EXCEL:
            if not filepath:
                raise ValueError("filepath is required for Excel export")
            self.export_excel(readings, filepath)
            return None

    def _flatten_dict(self, d: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
        """Flatten a nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                items.append((new_key, json.dumps(v, default=str)))
            else:
                items.append((new_key, v))
        return dict(items)


class ReportGenerator:
    """Generate summary reports from telemetry data."""

    def __init__(self, exporter: TelemetryExporter | None = None):
        self.exporter = exporter or TelemetryExporter()

    def generate_summary_report(self, device_id: str, readings: list[dict[str, Any]],
                                 analysis: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generate a summary report for a device."""
        if not readings:
            return {"device_id": device_id, "status": "no_data"}

        metrics = {}
        for reading in readings:
            metric = reading.get("metric")
            if metric not in metrics:
                metrics[metric] = {
                    "values": [],
                    "unit": reading.get("unit"),
                    "timestamps": [],
                }
            metrics[metric]["values"].append(reading.get("value"))
            metrics[metric]["timestamps"].append(reading.get("timestamp"))

        summary = {
            "device_id": device_id,
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "total_readings": len(readings),
            "time_range": {
                "earliest": min(r.get("timestamp", "") for r in readings) if readings else None,
                "latest": max(r.get("timestamp", "") for r in readings) if readings else None,
            },
            "metrics_summary": {},
        }

        for metric, data in metrics.items():
            values = data["values"]
            if values:
                summary["metrics_summary"][metric] = {
                    "unit": data["unit"],
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                    "latest": values[-1],
                }

        if analysis:
            summary["analysis"] = analysis

        return summary

    def export_summary_report(self, report: dict[str, Any], format: str, filepath: str | None = None) -> str | None:
        """Export a summary report."""
        data = [report]
        if format == ExportFormat.JSON:
            return self.exporter.export_json(data, pretty=True)
        elif format == ExportFormat.CSV:
            return self.exporter.export_csv(data)
        else:
            raise ValueError(f"Unsupported report format: {format}")
