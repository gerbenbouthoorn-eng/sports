"""
Activity analyzer — computes metrics and summaries from parsed FIT data.

Works with the FitData objects returned by fit_parser.parse_fit().
"""

import statistics
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from fit_parser import FitData, Record, Lap


# ---------------------------------------------------------------------------
# Heart rate zones (5-zone model, percentage of max HR)
# ---------------------------------------------------------------------------

ZONE_BOUNDARIES = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
ZONE_NAMES = ["Zone 1 (Recovery)", "Zone 2 (Aerobic)", "Zone 3 (Tempo)",
              "Zone 4 (Threshold)", "Zone 5 (Anaerobic)"]


def hr_zone(heart_rate: int, max_hr: int) -> int:
    """Return the HR zone (1-5) for a given heart rate and max HR."""
    pct = heart_rate / max_hr
    for i, upper in enumerate(ZONE_BOUNDARIES[1:], start=1):
        if pct <= upper:
            return i
    return 5


def hr_zone_distribution(records: list[Record], max_hr: int) -> dict[str, float]:
    """
    Compute percentage of time spent in each HR zone.

    Returns a dict mapping zone name -> percentage (0-100).
    """
    hr_records = [r for r in records if r.heart_rate is not None]
    if not hr_records:
        return {}

    counts = {name: 0 for name in ZONE_NAMES}
    for r in hr_records:
        zone_idx = hr_zone(r.heart_rate, max_hr) - 1
        counts[ZONE_NAMES[zone_idx]] += 1

    total = len(hr_records)
    return {name: round(count / total * 100, 1) for name, count in counts.items()}


# ---------------------------------------------------------------------------
# Running-specific metrics
# ---------------------------------------------------------------------------

def elevation_gain(records: list[Record]) -> float:
    """Total elevation gain in metres from sequential altitude samples."""
    gain = 0.0
    prev = None
    for r in records:
        if r.altitude is not None:
            if prev is not None and r.altitude > prev:
                gain += r.altitude - prev
            prev = r.altitude
    return round(gain, 1)


def elevation_loss(records: list[Record]) -> float:
    """Total elevation loss in metres."""
    loss = 0.0
    prev = None
    for r in records:
        if r.altitude is not None:
            if prev is not None and r.altitude < prev:
                loss += prev - r.altitude
            prev = r.altitude
    return round(loss, 1)


def best_pace_over_distance(records: list[Record], distance_m: float) -> Optional[float]:
    """
    Find the best (fastest) average pace over a rolling window of `distance_m` metres.

    Returns pace in min/km, or None if insufficient data.
    """
    dist_records = [r for r in records if r.distance is not None and r.timestamp is not None]
    if len(dist_records) < 2:
        return None

    best_pace = None
    left = 0
    for right in range(1, len(dist_records)):
        while (dist_records[right].distance - dist_records[left].distance) > distance_m:
            left += 1
        span_dist = dist_records[right].distance - dist_records[left].distance
        if span_dist >= distance_m:
            span_time = (dist_records[right].timestamp - dist_records[left].timestamp).total_seconds()
            if span_time > 0:
                pace = span_time / 60 / (span_dist / 1000)  # min/km
                if best_pace is None or pace < best_pace:
                    best_pace = pace
    return round(best_pace, 2) if best_pace else None


def average_running_dynamics(records: list[Record]) -> dict:
    """Compute mean vertical oscillation and ground contact time."""
    vo = [r.vertical_oscillation for r in records if r.vertical_oscillation is not None]
    gct = [r.ground_contact_time for r in records if r.ground_contact_time is not None]
    return {
        "avg_vertical_oscillation_mm": round(statistics.mean(vo), 1) if vo else None,
        "avg_ground_contact_time_ms": round(statistics.mean(gct), 1) if gct else None,
    }


# ---------------------------------------------------------------------------
# Cycling-specific metrics
# ---------------------------------------------------------------------------

def normalized_power(records: list[Record], window_seconds: int = 30) -> Optional[int]:
    """
    Calculate Normalized Power (NP) using the standard 30-second rolling average method.

    Returns NP in watts, or None if no power data is available.
    """
    powers = [r.power for r in records if r.power is not None]
    if len(powers) < window_seconds:
        return None

    rolling_avgs = []
    for i in range(window_seconds - 1, len(powers)):
        window = powers[i - window_seconds + 1 : i + 1]
        rolling_avgs.append(statistics.mean(window))

    np_val = (statistics.mean(v**4 for v in rolling_avgs)) ** 0.25
    return int(round(np_val))


def training_stress_score(np_watts: int, ftp: int, duration_seconds: float) -> float:
    """
    Calculate Training Stress Score (TSS).

    TSS = (duration_s * NP * IF) / (FTP * 3600) * 100
    where IF = NP / FTP.
    """
    if_val = np_watts / ftp
    tss = (duration_seconds * np_watts * if_val) / (ftp * 3600) * 100
    return round(tss, 1)


def intensity_factor(np_watts: int, ftp: int) -> float:
    """Intensity Factor = NP / FTP."""
    return round(np_watts / ftp, 3)


def power_zone_distribution(records: list[Record], ftp: int) -> dict[str, float]:
    """
    Percentage of time spent in each power zone (Coggan 7-zone model).

    Zones are defined as percentages of FTP:
      Z1 <55%, Z2 56-75%, Z3 76-90%, Z4 91-105%, Z5 106-120%, Z6 121-150%, Z7 >150%
    """
    boundaries = [0.55, 0.75, 0.90, 1.05, 1.20, 1.50]
    zone_names = ["Z1 Active Recovery", "Z2 Endurance", "Z3 Tempo",
                  "Z4 Lactate Threshold", "Z5 VO2max", "Z6 Anaerobic", "Z7 Neuromuscular"]
    power_records = [r for r in records if r.power is not None]
    if not power_records:
        return {}

    counts = {name: 0 for name in zone_names}
    for r in power_records:
        pct = r.power / ftp
        zone_idx = len(boundaries)
        for i, upper in enumerate(boundaries):
            if pct <= upper:
                zone_idx = i
                break
        counts[zone_names[zone_idx]] += 1

    total = len(power_records)
    return {name: round(count / total * 100, 1) for name, count in counts.items()}


# ---------------------------------------------------------------------------
# General summary
# ---------------------------------------------------------------------------

@dataclass
class ActivitySummary:
    sport: str
    start_time: object
    total_distance_km: float
    moving_time_min: float
    elapsed_time_min: float
    avg_pace_min_km: Optional[float]
    avg_speed_kmh: float
    avg_heart_rate: Optional[int]
    max_heart_rate: Optional[int]
    elevation_gain_m: float
    elevation_loss_m: float
    calories: Optional[int]
    laps: int
    # Running extras
    avg_cadence: Optional[int] = None
    best_1k_pace: Optional[float] = None
    running_dynamics: Optional[dict] = None
    hr_zones: Optional[dict] = None
    # Cycling extras
    avg_power: Optional[int] = None
    normalized_power_w: Optional[int] = None
    tss: Optional[float] = None
    intensity_factor: Optional[float] = None
    power_zones: Optional[dict] = None


def summarize(data: FitData, max_hr: int = None, ftp: int = None) -> ActivitySummary:
    """
    Produce a high-level ActivitySummary from a FitData object.

    Args:
        data:   Parsed FIT data.
        max_hr: User's max heart rate for zone calculations.
        ftp:    Functional Threshold Power in watts (cycling).
    """
    s = data.session
    records = data.records

    dist_km = (s.total_distance or 0) / 1000
    moving_min = (s.total_timer_time or 0) / 60
    elapsed_min = (s.total_elapsed_time or 0) / 60
    avg_speed_kmh = (s.avg_speed or 0) * 3.6
    avg_pace = (moving_min / dist_km) if dist_km > 0 else None

    elev_gain = elevation_gain(records)
    elev_loss = elevation_loss(records)

    hr_zones = None
    if max_hr:
        hr_zones = hr_zone_distribution(records, max_hr)

    dyn = average_running_dynamics(records)
    best_1k = best_pace_over_distance(records, 1000)

    np_w = None
    tss_val = None
    if_val = None
    pz = None
    if ftp:
        np_w = normalized_power(records)
        if np_w:
            tss_val = training_stress_score(np_w, ftp, s.total_timer_time or 0)
            if_val = intensity_factor(np_w, ftp)
        pz = power_zone_distribution(records, ftp)

    return ActivitySummary(
        sport=s.sport,
        start_time=s.start_time,
        total_distance_km=round(dist_km, 2),
        moving_time_min=round(moving_min, 1),
        elapsed_time_min=round(elapsed_min, 1),
        avg_pace_min_km=round(avg_pace, 2) if avg_pace else None,
        avg_speed_kmh=round(avg_speed_kmh, 2),
        avg_heart_rate=s.avg_heart_rate,
        max_heart_rate=s.max_heart_rate,
        elevation_gain_m=elev_gain,
        elevation_loss_m=elev_loss,
        calories=s.total_calories,
        laps=len(data.laps),
        avg_cadence=s.avg_cadence,
        best_1k_pace=best_1k,
        running_dynamics=dyn if any(dyn.values()) else None,
        hr_zones=hr_zones,
        avg_power=s.avg_power,
        normalized_power_w=np_w,
        tss=tss_val,
        intensity_factor=if_val,
        power_zones=pz,
    )


def print_summary(summary: ActivitySummary) -> None:
    """Pretty-print an ActivitySummary."""

    def _fmt_pace(p):
        if p is None:
            return "N/A"
        m = int(p)
        s = int((p - m) * 60)
        return f"{m}:{s:02d} min/km"

    print(f"Sport:           {summary.sport}")
    print(f"Start:           {summary.start_time}")
    print(f"Distance:        {summary.total_distance_km} km")
    print(f"Moving time:     {summary.moving_time_min} min")
    print(f"Elapsed time:    {summary.elapsed_time_min} min")
    print(f"Avg pace:        {_fmt_pace(summary.avg_pace_min_km)}")
    print(f"Avg speed:       {summary.avg_speed_kmh} km/h")
    print(f"Avg HR:          {summary.avg_heart_rate} bpm")
    print(f"Max HR:          {summary.max_heart_rate} bpm")
    print(f"Elevation gain:  {summary.elevation_gain_m} m")
    print(f"Elevation loss:  {summary.elevation_loss_m} m")
    print(f"Calories:        {summary.calories} kcal")
    print(f"Laps:            {summary.laps}")

    if summary.avg_cadence:
        print(f"Avg cadence:     {summary.avg_cadence} spm")
    if summary.best_1k_pace:
        print(f"Best 1km pace:   {_fmt_pace(summary.best_1k_pace)}")
    if summary.running_dynamics:
        dyn = summary.running_dynamics
        print(f"Vert. osc.:      {dyn['avg_vertical_oscillation_mm']} mm")
        print(f"GCT:             {dyn['avg_ground_contact_time_ms']} ms")
    if summary.hr_zones:
        print("\nHR Zones:")
        for zone, pct in summary.hr_zones.items():
            print(f"  {zone}: {pct}%")
    if summary.avg_power:
        print(f"\nAvg power:       {summary.avg_power} W")
    if summary.normalized_power_w:
        print(f"NP:              {summary.normalized_power_w} W")
    if summary.intensity_factor:
        print(f"IF:              {summary.intensity_factor}")
    if summary.tss:
        print(f"TSS:             {summary.tss}")
    if summary.power_zones:
        print("\nPower Zones:")
        for zone, pct in summary.power_zones.items():
            print(f"  {zone}: {pct}%")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    from fit_parser import parse_fit, parse_fit_from_zip

    parser = argparse.ArgumentParser(description="Analyze a Garmin .fit file")
    parser.add_argument("file", help=".fit or .zip file path")
    parser.add_argument("--max-hr", type=int, help="Max heart rate for zone calc")
    parser.add_argument("--ftp", type=int, help="FTP in watts for cycling metrics")
    args = parser.parse_args()

    data = parse_fit_from_zip(args.file) if args.file.endswith(".zip") else parse_fit(args.file)
    summary = summarize(data, max_hr=args.max_hr, ftp=args.ftp)
    print_summary(summary)
