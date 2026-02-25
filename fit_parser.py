"""
FIT file parser — reads Garmin .fit files and extracts structured data.

Requires: fitparse
    pip install fitparse
"""

import zipfile
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

import fitparse


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Record:
    """A single data record (typically one GPS/sensor sample per second)."""
    timestamp: datetime = None
    latitude: float = None
    longitude: float = None
    altitude: float = None          # metres
    distance: float = None          # metres
    speed: float = None             # m/s
    heart_rate: int = None          # bpm
    cadence: int = None             # rpm or steps/min
    power: int = None               # watts
    temperature: float = None       # °C
    vertical_oscillation: float = None  # mm
    ground_contact_time: float = None   # ms
    extra: dict = field(default_factory=dict)

    @property
    def speed_kmh(self) -> float | None:
        return self.speed * 3.6 if self.speed is not None else None

    @property
    def pace_min_per_km(self) -> float | None:
        """Running pace in min/km."""
        if self.speed and self.speed > 0:
            return 1000 / (self.speed * 60)
        return None


@dataclass
class Lap:
    timestamp: datetime = None
    start_time: datetime = None
    total_elapsed_time: float = None    # seconds
    total_distance: float = None        # metres
    avg_speed: float = None             # m/s
    max_speed: float = None             # m/s
    avg_heart_rate: int = None
    max_heart_rate: int = None
    avg_cadence: int = None
    avg_power: int = None
    total_ascent: float = None          # metres
    total_descent: float = None         # metres
    extra: dict = field(default_factory=dict)


@dataclass
class Session:
    sport: str = None
    sub_sport: str = None
    start_time: datetime = None
    total_elapsed_time: float = None    # seconds
    total_timer_time: float = None      # seconds (excludes pauses)
    total_distance: float = None        # metres
    avg_speed: float = None             # m/s
    max_speed: float = None             # m/s
    avg_heart_rate: int = None
    max_heart_rate: int = None
    avg_cadence: int = None
    avg_power: int = None
    normalized_power: int = None
    total_ascent: float = None
    total_descent: float = None
    total_calories: int = None
    training_stress_score: float = None
    intensity_factor: float = None
    extra: dict = field(default_factory=dict)


@dataclass
class FitData:
    session: Session = field(default_factory=Session)
    laps: list[Lap] = field(default_factory=list)
    records: list[Record] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_KNOWN_FIELDS = {
    # (fitparse field name) -> (dataclass attribute, scale)
    "timestamp": ("timestamp", None),
    "position_lat": ("latitude", 180 / 2**31),
    "position_long": ("longitude", 180 / 2**31),
    "altitude": ("altitude", None),
    "distance": ("distance", None),
    "speed": ("speed", None),
    "heart_rate": ("heart_rate", None),
    "cadence": ("cadence", None),
    "power": ("power", None),
    "temperature": ("temperature", None),
    "vertical_oscillation": ("vertical_oscillation", None),
    "stance_time": ("ground_contact_time", None),
}

_SESSION_FIELDS = {
    "sport": ("sport", None),
    "sub_sport": ("sub_sport", None),
    "start_time": ("start_time", None),
    "total_elapsed_time": ("total_elapsed_time", None),
    "total_timer_time": ("total_timer_time", None),
    "total_distance": ("total_distance", None),
    "avg_speed": ("avg_speed", None),
    "max_speed": ("max_speed", None),
    "avg_heart_rate": ("avg_heart_rate", None),
    "max_heart_rate": ("max_heart_rate", None),
    "avg_cadence": ("avg_cadence", None),
    "avg_power": ("avg_power", None),
    "normalized_power": ("normalized_power", None),
    "total_ascent": ("total_ascent", None),
    "total_descent": ("total_descent", None),
    "total_calories": ("total_calories", None),
    "training_stress_score": ("training_stress_score", None),
    "intensity_factor": ("intensity_factor", None),
}

_LAP_FIELDS = {
    "timestamp": ("timestamp", None),
    "start_time": ("start_time", None),
    "total_elapsed_time": ("total_elapsed_time", None),
    "total_distance": ("total_distance", None),
    "avg_speed": ("avg_speed", None),
    "max_speed": ("max_speed", None),
    "avg_heart_rate": ("avg_heart_rate", None),
    "max_heart_rate": ("max_heart_rate", None),
    "avg_cadence": ("avg_cadence", None),
    "avg_power": ("avg_power", None),
    "total_ascent": ("total_ascent", None),
    "total_descent": ("total_descent", None),
}


def _apply_fields(obj, message, field_map: dict) -> None:
    for fit_name, (attr, scale) in field_map.items():
        val = message.get_value(fit_name)
        if val is not None:
            if scale is not None:
                val = val * scale
            setattr(obj, attr, val)
        else:
            # stash unknown fields in .extra
            pass
    # Collect remaining fields into .extra
    known = set(field_map.keys())
    for f in message.fields:
        if f.name not in known and f.value is not None:
            obj.extra[f.name] = f.value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_fit(path: str) -> FitData:
    """
    Parse a .fit file and return a FitData object.

    Args:
        path: Path to a .fit file.
    """
    data = FitData()
    ff = fitparse.FitFile(path)

    for message in ff.get_messages():
        name = message.name
        if name == "record":
            rec = Record()
            _apply_fields(rec, message, _KNOWN_FIELDS)
            data.records.append(rec)
        elif name == "lap":
            lap = Lap()
            _apply_fields(lap, message, _LAP_FIELDS)
            data.laps.append(lap)
        elif name == "session":
            _apply_fields(data.session, message, _SESSION_FIELDS)

    return data


def parse_fit_from_zip(zip_path: str) -> FitData:
    """
    Extract and parse a .fit file from a Garmin activity ZIP archive.

    The ZIP downloaded from Garmin Connect contains a single .fit file.
    """
    with zipfile.ZipFile(zip_path) as zf:
        fit_names = [n for n in zf.namelist() if n.endswith(".fit")]
        if not fit_names:
            raise ValueError(f"No .fit file found inside {zip_path}")
        with zf.open(fit_names[0]) as fit_file:
            import io
            buf = io.BytesIO(fit_file.read())
            ff = fitparse.FitFile(buf)
            data = FitData()
            for message in ff.get_messages():
                name = message.name
                if name == "record":
                    rec = Record()
                    _apply_fields(rec, message, _KNOWN_FIELDS)
                    data.records.append(rec)
                elif name == "lap":
                    lap = Lap()
                    _apply_fields(lap, message, _LAP_FIELDS)
                    data.laps.append(lap)
                elif name == "session":
                    _apply_fields(data.session, message, _SESSION_FIELDS)
            return data


def iter_records(path: str) -> Iterator[Record]:
    """Lazy iterator over records in a .fit file — memory-efficient for large files."""
    ff = fitparse.FitFile(path)
    for message in ff.get_messages("record"):
        rec = Record()
        _apply_fields(rec, message, _KNOWN_FIELDS)
        yield rec


def records_to_dicts(records: list[Record]) -> list[dict]:
    """Convert a list of Record objects to plain dicts (e.g. for DataFrame creation)."""
    return [
        {
            "timestamp": r.timestamp,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "altitude": r.altitude,
            "distance": r.distance,
            "speed_ms": r.speed,
            "speed_kmh": r.speed_kmh,
            "pace_min_km": r.pace_min_per_km,
            "heart_rate": r.heart_rate,
            "cadence": r.cadence,
            "power": r.power,
            "temperature": r.temperature,
        }
        for r in records
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Parse a Garmin .fit file")
    parser.add_argument("file", help=".fit or .zip file path")
    parser.add_argument(
        "--output",
        choices=["summary", "records", "laps"],
        default="summary",
    )
    args = parser.parse_args()

    if args.file.endswith(".zip"):
        data = parse_fit_from_zip(args.file)
    else:
        data = parse_fit(args.file)

    def default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    if args.output == "summary":
        s = data.session
        print(f"Sport:        {s.sport} / {s.sub_sport}")
        print(f"Start:        {s.start_time}")
        dist_km = (s.total_distance or 0) / 1000
        print(f"Distance:     {dist_km:.2f} km")
        mins = (s.total_timer_time or 0) / 60
        print(f"Moving time:  {mins:.1f} min")
        print(f"Avg HR:       {s.avg_heart_rate} bpm")
        print(f"Max HR:       {s.max_heart_rate} bpm")
        print(f"Calories:     {s.total_calories} kcal")
        print(f"Laps:         {len(data.laps)}")
        print(f"Records:      {len(data.records)}")
    elif args.output == "records":
        print(json.dumps(records_to_dicts(data.records), default=default, indent=2))
    elif args.output == "laps":
        print(json.dumps([l.__dict__ for l in data.laps], default=default, indent=2))
