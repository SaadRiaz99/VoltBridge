"""Advanced analytics module for telemetry data with trend analysis and anomaly detection."""
import math
from datetime import datetime, timezone
from typing import Any
from statistics import fmean, stdev
from .models import UNITS


class TrendDirection:
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


class AnomalyType:
    SPIKE = "spike"
    DROP = "drop"
    DRIFT = "drift"
    OUTLIER = "outlier"


class TelemetryAnalytics:
    """Advanced analytics for electrical telemetry data."""

    def __init__(self, z_threshold: float = 2.5, trend_window: int = 10):
        self.z_threshold = z_threshold
        self.trend_window = trend_window

    def calculate_statistics(self, values: list[float]) -> dict[str, Any]:
        """Calculate comprehensive statistics for a set of values."""
        if not values:
            return {"count": 0, "min": None, "max": None, "mean": None, "std": None, "median": None}

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mean_val = fmean(sorted_vals)
        std_val = stdev(sorted_vals) if n > 1 else 0.0

        # Calculate median
        if n % 2 == 1:
            median_val = sorted_vals[n // 2]
        else:
            median_val = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2

        # Calculate percentiles
        p25 = sorted_vals[int(n * 0.25)]
        p75 = sorted_vals[int(n * 0.75)]
        iqr = p75 - p25

        return {
            "count": n,
            "min": min(sorted_vals),
            "max": max(sorted_vals),
            "mean": mean_val,
            "std": std_val,
            "median": median_val,
            "percentile_25": p25,
            "percentile_75": p75,
            "iqr": iqr,
            "range": max(sorted_vals) - min(sorted_vals),
            "coefficient_of_variation": (std_val / mean_val * 100) if mean_val != 0 else None,
        }

    def detect_anomalies(self, values: list[float], timestamps: list[datetime] | None = None) -> list[dict[str, Any]]:
        """Detect anomalies using Z-score and IQR methods."""
        if len(values) < 3:
            return []

        stats = self.calculate_statistics(values)
        mean_val = stats["mean"]
        std_val = stats["std"]
        iqr = stats["iqr"]
        p25 = stats["percentile_25"]
        p75 = stats["percentile_75"]

        anomalies = []
        for i, val in enumerate(values):
            anomaly_types = []
            confidence = 0.0

            # Z-score detection
            if std_val > 0:
                z_score = abs(val - mean_val) / std_val
                if z_score > self.z_threshold:
                    anomaly_types.append(AnomalyType.OUTLIER)
                    confidence = min(z_score / (self.z_threshold * 2), 1.0)

            # IQR-based detection
            lower_bound = p25 - 1.5 * iqr
            upper_bound = p75 + 1.5 * iqr
            if val < lower_bound:
                anomaly_types.append(AnomalyType.DROP)
                confidence = max(confidence, min((lower_bound - val) / (iqr + 1e-10), 1.0))
            elif val > upper_bound:
                anomaly_types.append(AnomalyType.SPIKE)
                confidence = max(confidence, min((val - upper_bound) / (iqr + 1e-10), 1.0))

            # Spike/drop detection based on neighbors
            if i > 0 and i < len(values) - 1:
                prev_diff = val - values[i - 1]
                next_diff = values[i + 1] - val
                if abs(prev_diff) > 2 * std_val and abs(next_diff) > 2 * std_val:
                    if AnomalyType.SPIKE not in anomaly_types and AnomalyType.DROP not in anomaly_types:
                        if prev_diff > 0 and next_diff < 0:
                            anomaly_types.append(AnomalyType.SPIKE)
                        elif prev_diff < 0 and next_diff > 0:
                            anomaly_types.append(AnomalyType.DROP)
                        confidence = max(confidence, 0.7)

            if anomaly_types:
                timestamp = timestamps[i].isoformat() if timestamps and i < len(timestamps) else None
                anomalies.append({
                    "index": i,
                    "value": val,
                    "types": anomaly_types,
                    "confidence": round(confidence, 3),
                    "timestamp": timestamp,
                    "z_score": round((val - mean_val) / (std_val + 1e-10), 3) if std_val > 0 else None,
                })

        return anomalies

    def analyze_trend(self, values: list[float], timestamps: list[datetime] | None = None) -> dict[str, Any]:
        """Analyze trend direction and stability using linear regression."""
        if len(values) < 2:
            return {"direction": TrendDirection.STABLE, "slope": 0, "r_squared": 0, "confidence": 0}

        n = len(values)
        x_vals = list(range(n))
        x_mean = fmean(x_vals)
        y_mean = fmean(values)

        # Linear regression
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)

        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator

        intercept = y_mean - slope * x_mean

        # Calculate R-squared
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_vals, values))
        ss_tot = sum((y - y_mean) ** 2 for y in values)
        r_squared = 1 - (ss_res / (ss_tot + 1e-10))

        # Determine trend direction
        std_val = stdev(values) if len(values) > 1 else 0
        slope_magnitude = abs(slope) / (std_val + 1e-10)

        if slope_magnitude < 0.1:
            direction = TrendDirection.STABLE
        elif slope_magnitude > 0.5:
            direction = TrendDirection.VOLATILE
        elif slope > 0:
            direction = TrendDirection.INCREASING
        else:
            direction = TrendDirection.DECREASING

        # Calculate volatility (coefficient of variation of differences)
        if len(values) > 1:
            diffs = [values[i] - values[i - 1] for i in range(1, len(values))]
            vol_mean = fmean(diffs)
            vol_std = stdev(diffs) if len(diffs) > 1 else 0
            volatility = vol_std / (abs(vol_mean) + 1e-10)
        else:
            volatility = 0

        return {
            "direction": direction,
            "slope": round(slope, 6),
            "intercept": round(intercept, 4),
            "r_squared": round(r_squared, 4),
            "confidence": round(min(r_squared * 100, 100), 2),
            "volatility": round(volatility, 4),
            "forecast_next": round(slope * n + intercept, 4) if values else None,
            "periods_analyzed": n,
        }

    def forecast_simple(self, values: list[float], periods: int = 5) -> dict[str, Any]:
        """Simple linear forecast based on historical trend."""
        if len(values) < 2 or periods < 1:
            return {"forecast": [], "method": "insufficient_data"}

        n = len(values)
        x_vals = list(range(n))
        x_mean = fmean(x_vals)
        y_mean = fmean(values)

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)

        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean

        forecast = []
        for i in range(1, periods + 1):
            predicted = slope * (n + i - 1) + intercept
            # Add confidence interval based on historical variance
            std_val = stdev(values) if len(values) > 1 else 0
            margin = 1.96 * std_val * math.sqrt(1 + i / n)

            forecast.append({
                "period": i,
                "predicted_value": round(predicted, 4),
                "lower_bound": round(predicted - margin, 4),
                "upper_bound": round(predicted + margin, 4),
            })

        return {
            "forecast": forecast,
            "method": "linear_regression",
            "slope": round(slope, 6),
            "confidence_level": 0.95,
        }

    def detect_patterns(self, values: list[float]) -> dict[str, Any]:
        """Detect common patterns in telemetry data."""
        if len(values) < 3:
            return {"patterns": [], "analysis": "insufficient_data"}

        patterns = []
        stats = self.calculate_statistics(values)
        trend = self.analyze_trend(values)

        # Check for cyclic patterns (simple peak/valley detection)
        peaks = []
        valleys = []
        for i in range(1, len(values) - 1):
            if values[i] > values[i - 1] and values[i] > values[i + 1]:
                peaks.append(i)
            elif values[i] < values[i - 1] and values[i] < values[i + 1]:
                valleys.append(i)

        if len(peaks) >= 2 and len(valleys) >= 2:
            patterns.append({
                "type": "cyclic",
                "description": f"Detected {len(peaks)} peaks and {len(valleys)} valleys",
                "confidence": min(len(peaks) / (len(values) / 4), 1.0),
            })

        # Check for plateau (stable periods)
        if stats["std"] is not None and stats["std"] < (abs(stats["mean"]) + 1e-10) * 0.05:
            patterns.append({
                "type": "plateau",
                "description": "Values are relatively stable with low variance",
                "confidence": 1 - (stats["std"] / (abs(stats["mean"]) + 1e-10)),
            })

        # Check for gradual drift
        if trend["direction"] in [TrendDirection.INCREASING, TrendDirection.DECREASING]:
            patterns.append({
                "type": "drift",
                "description": f"Gradual {trend['direction']} trend detected",
                "confidence": trend["confidence"] / 100,
            })

        # Check for spikes
        anomalies = self.detect_anomalies(values)
        spike_count = sum(1 for a in anomalies if AnomalyType.SPIKE in a["types"])
        if spike_count > 0:
            patterns.append({
                "type": "intermittent_spikes",
                "description": f"Detected {spike_count} spike anomalies",
                "confidence": min(spike_count / (len(values) * 0.1), 1.0),
            })

        return {
            "patterns": patterns,
            "statistics": stats,
            "trend": trend,
            "anomaly_count": len(anomalies),
            "analysis": "pattern_detection_complete",
        }


def analyze_device_history(readings: list[dict], metric: str) -> dict[str, Any]:
    """Analyze historical readings for a specific metric."""
    if not readings:
        return {"metric": metric, "analysis": "no_data"}

    values = [r["value"] for r in readings if r.get("metric") == metric and r.get("usable", True)]
    timestamps = []
    for r in readings:
        if r.get("metric") == metric and r.get("usable", True) and "timestamp" in r:
            try:
                ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                timestamps.append(ts)
            except (ValueError, TypeError):
                pass

    if not values:
        return {"metric": metric, "analysis": "no_usable_data"}

    analytics = TelemetryAnalytics()
    stats = analytics.calculate_statistics(values)
    trend = analytics.analyze_trend(values, timestamps if len(timestamps) == len(values) else None)
    anomalies = analytics.detect_anomalies(values, timestamps if len(timestamps) == len(values) else None)
    patterns = analytics.detect_patterns(values)
    forecast = analytics.forecast_simple(values, periods=5)

    return {
        "metric": metric,
        "unit": UNITS.get(metric, "unknown"),
        "statistics": stats,
        "trend": trend,
        "anomalies": anomalies,
        "patterns": patterns,
        "forecast": forecast,
        "data_points_analyzed": len(values),
    }
