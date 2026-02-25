"""
Garmin Connect API client for fetching activities, health metrics, and user data.

Requires: garminconnect
    pip install garminconnect
"""

import json
import os
from datetime import date, timedelta
from garminconnect import Garmin


def get_client(email: str = None, password: str = None) -> Garmin:
    """
    Create and authenticate a Garmin Connect client.

    Credentials are read from arguments or environment variables:
        GARMIN_EMAIL, GARMIN_PASSWORD

    Returns an authenticated Garmin client instance.
    """
    email = email or os.environ["GARMIN_EMAIL"]
    password = password or os.environ["GARMIN_PASSWORD"]
    client = Garmin(email, password)
    client.login()
    return client


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

def get_activities(client: Garmin, start: int = 0, limit: int = 20) -> list[dict]:
    """Fetch a page of recent activities."""
    return client.get_activities(start, limit)


def get_activities_by_date(
    client: Garmin,
    start_date: str,
    end_date: str,
    activity_type: str = None,
) -> list[dict]:
    """
    Fetch activities between two dates (inclusive).

    Args:
        start_date: ISO date string, e.g. "2024-01-01"
        end_date:   ISO date string, e.g. "2024-01-31"
        activity_type: Optional filter, e.g. "running", "cycling"
    """
    return client.get_activities_by_date(start_date, end_date, activity_type)


def get_activity_details(client: Garmin, activity_id: int) -> dict:
    """Fetch detailed data for a single activity."""
    return client.get_activity_details(activity_id)


def download_fit_file(client: Garmin, activity_id: int, output_dir: str = ".") -> str:
    """
    Download the original .fit file for an activity.

    Returns the path to the saved file.
    """
    data = client.download_activity(activity_id, dl_fmt=client.ActivityDownloadFormat.ORIGINAL)
    path = os.path.join(output_dir, f"{activity_id}.zip")
    with open(path, "wb") as f:
        f.write(data)
    return path


# ---------------------------------------------------------------------------
# Health & Wellness
# ---------------------------------------------------------------------------

def get_steps(client: Garmin, target_date: str = None) -> dict:
    """Daily step count. Defaults to today."""
    target_date = target_date or str(date.today())
    return client.get_steps_data(target_date)


def get_heart_rate(client: Garmin, target_date: str = None) -> dict:
    """Resting and intraday heart rate data for a given date."""
    target_date = target_date or str(date.today())
    return client.get_heart_rates(target_date)


def get_sleep(client: Garmin, target_date: str = None) -> dict:
    """Sleep data (stages, scores) for a given date."""
    target_date = target_date or str(date.today())
    return client.get_sleep_data(target_date)


def get_body_composition(client: Garmin, start_date: str, end_date: str) -> dict:
    """Body composition (weight, BMI, body fat) for a date range."""
    return client.get_body_composition(start_date, end_date)


def get_stress(client: Garmin, target_date: str = None) -> dict:
    """Stress level data for a given date."""
    target_date = target_date or str(date.today())
    return client.get_stress_data(target_date)


def get_training_readiness(client: Garmin, target_date: str = None) -> dict:
    """Training readiness score for a given date."""
    target_date = target_date or str(date.today())
    return client.get_training_readiness(target_date)


def get_hrv(client: Garmin, target_date: str = None) -> dict:
    """Heart rate variability (HRV) data for a given date."""
    target_date = target_date or str(date.today())
    return client.get_hrv_data(target_date)


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

def get_user_profile(client: Garmin) -> dict:
    """Fetch the authenticated user's profile information."""
    return client.get_user_profile()


def get_personal_records(client: Garmin) -> list[dict]:
    """Fetch the user's personal records (PRs) across activity types."""
    return client.get_personal_record()


def get_device_list(client: Garmin) -> list[dict]:
    """List all Garmin devices linked to the account."""
    return client.get_devices()


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

def print_json(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Garmin Connect CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("profile", help="Print user profile")
    sub.add_parser("devices", help="List linked devices")
    sub.add_parser("records", help="Print personal records")

    act_p = sub.add_parser("activities", help="List recent activities")
    act_p.add_argument("--limit", type=int, default=10)

    health_p = sub.add_parser("health", help="Print today's health summary")
    health_p.add_argument("--date", default=str(date.today()))

    args = parser.parse_args()
    client = get_client()

    if args.command == "profile":
        print_json(get_user_profile(client))
    elif args.command == "devices":
        print_json(get_device_list(client))
    elif args.command == "records":
        print_json(get_personal_records(client))
    elif args.command == "activities":
        print_json(get_activities(client, limit=args.limit))
    elif args.command == "health":
        print("--- Steps ---")
        print_json(get_steps(client, args.date))
        print("--- Heart Rate ---")
        print_json(get_heart_rate(client, args.date))
        print("--- Sleep ---")
        print_json(get_sleep(client, args.date))
        print("--- Stress ---")
        print_json(get_stress(client, args.date))
        print("--- HRV ---")
        print_json(get_hrv(client, args.date))
    else:
        parser.print_help()
