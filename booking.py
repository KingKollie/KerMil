"""
KerMil booking module — services, availability, and appointment scheduling.

Design notes:
- Every public function returns a consistent dict shape: {"success": bool, ...}
  Never returns None, so callers can safely check result["success"].
- Availability is computed live from three inputs: her recurring weekly hours,
  one-off blocked times, and existing confirmed appointments — nothing is
  pre-materialized into a calendar table, so there's no sync bug between
  "the schedule" and "the appointments."
"""

import os
import logging
from datetime import datetime, timedelta, date as date_cls, time as time_cls

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("kermil.booking")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

REQUEST_TIMEOUT = 10.0
SLOT_STEP_MINUTES = 30  # granularity of bookable start times, e.g. 9:00, 9:30, 10:00...


# ── HELPERS ──────────────────────────────────────────────────────────

def _parse_time(t: str) -> time_cls:
    """Supabase returns time as 'HH:MM:SS' — parse to a comparable time object."""
    return datetime.strptime(t[:8], "%H:%M:%S").time()


def _is_admin(user_id: str) -> bool:
    try:
        res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}&select=is_admin",
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        data = res.json()
        return bool(data and data[0].get("is_admin"))
    except (httpx.RequestError, ValueError, IndexError, KeyError):
        return False


# ── SERVICES (public read, admin write) ─────────────────────────────

def get_services() -> dict:
    try:
        res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/services?active=eq.true&order=category,name",
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code >= 400:
            return {"success": False, "error": "Could not load services."}
        return {"success": True, "services": res.json()}
    except httpx.RequestError as e:
        logger.error("get_services failed: %s", e)
        return {"success": False, "error": "Could not reach the database."}


def admin_create_service(admin_user_id: str, name: str, description: str,
                          duration_minutes: int, price: float, category: str) -> dict:
    if not _is_admin(admin_user_id):
        return {"success": False, "error": "Not authorized."}
    if duration_minutes <= 0 or price < 0:
        return {"success": False, "error": "Invalid duration or price."}
    try:
        res = httpx.post(
            f"{SUPABASE_URL}/rest/v1/services",
            headers={**HEADERS, "Prefer": "return=representation"},
            json={
                "name": name, "description": description,
                "duration_minutes": duration_minutes, "price": price, "category": category,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code >= 400:
            return {"success": False, "error": "Could not create service."}
        return {"success": True, "service": res.json()[0]}
    except (httpx.RequestError, IndexError) as e:
        logger.error("admin_create_service failed: %s", e)
        return {"success": False, "error": "Could not create service."}


def admin_update_service(admin_user_id: str, service_id: str, updates: dict) -> dict:
    if not _is_admin(admin_user_id):
        return {"success": False, "error": "Not authorized."}
    try:
        res = httpx.patch(
            f"{SUPABASE_URL}/rest/v1/services?id=eq.{service_id}",
            headers={**HEADERS, "Prefer": "return=representation"},
            json=updates,
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code >= 400:
            return {"success": False, "error": "Could not update service."}
        return {"success": True, "service": res.json()[0]}
    except (httpx.RequestError, IndexError) as e:
        logger.error("admin_update_service failed: %s", e)
        return {"success": False, "error": "Could not update service."}


def admin_delete_service(admin_user_id: str, service_id: str) -> dict:
    if not _is_admin(admin_user_id):
        return {"success": False, "error": "Not authorized."}
    try:
        # Soft delete — keeps history for past appointments referencing this service intact.
        res = httpx.patch(
            f"{SUPABASE_URL}/rest/v1/services?id=eq.{service_id}",
            headers=HEADERS,
            json={"active": False},
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code >= 400:
            return {"success": False, "error": "Could not remove service."}
        return {"success": True}
    except httpx.RequestError as e:
        logger.error("admin_delete_service failed: %s", e)
        return {"success": False, "error": "Could not remove service."}


# ── AVAILABILITY (admin sets hours + blocks) ────────────────────────

def admin_set_weekly_availability(admin_user_id: str, day_of_week: int,
                                   start_time: str, end_time: str) -> dict:
    if not _is_admin(admin_user_id):
        return {"success": False, "error": "Not authorized."}
    if not (0 <= day_of_week <= 6):
        return {"success": False, "error": "day_of_week must be 0 (Sunday) through 6 (Saturday)."}
    try:
        res = httpx.post(
            f"{SUPABASE_URL}/rest/v1/provider_availability",
            headers={**HEADERS, "Prefer": "return=representation"},
            json={"day_of_week": day_of_week, "start_time": start_time, "end_time": end_time},
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code >= 400:
            return {"success": False, "error": "Could not set availability."}
        return {"success": True, "availability": res.json()[0]}
    except (httpx.RequestError, IndexError) as e:
        logger.error("admin_set_weekly_availability failed: %s", e)
        return {"success": False, "error": "Could not set availability."}


def admin_block_time(admin_user_id: str, block_date: str, full_day: bool = True,
                      start_time: str = None, end_time: str = None, reason: str = "") -> dict:
    if not _is_admin(admin_user_id):
        return {"success": False, "error": "Not authorized."}
    try:
        res = httpx.post(
            f"{SUPABASE_URL}/rest/v1/blocked_times",
            headers={**HEADERS, "Prefer": "return=representation"},
            json={
                "block_date": block_date, "full_day": full_day,
                "start_time": start_time, "end_time": end_time, "reason": reason,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code >= 400:
            return {"success": False, "error": "Could not block time."}
        return {"success": True, "block": res.json()[0]}
    except (httpx.RequestError, IndexError) as e:
        logger.error("admin_block_time failed: %s", e)
        return {"success": False, "error": "Could not block time."}


# ── SLOT COMPUTATION (the actual scheduling logic) ──────────────────

def get_available_slots(service_id: str, target_date: str) -> dict:
    """
    Returns bookable start times (as 'HH:MM' strings) for a given service on a given date,
    accounting for weekly hours, blocked times, and existing confirmed appointments.
    """
    try:
        parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        return {"success": False, "error": "Date must be in YYYY-MM-DD format."}

    if parsed_date < date_cls.today():
        return {"success": False, "error": "Cannot book a date in the past."}

    # 1. Get the service's duration
    try:
        svc_res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/services?id=eq.{service_id}&select=duration_minutes",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        svc_data = svc_res.json()
        if not svc_data:
            return {"success": False, "error": "Service not found."}
        duration = timedelta(minutes=svc_data[0]["duration_minutes"])
    except (httpx.RequestError, ValueError) as e:
        logger.error("get_available_slots: service lookup failed: %s", e)
        return {"success": False, "error": "Could not load service."}

    # 2. Get recurring weekly availability windows for this day of week
    day_of_week = parsed_date.weekday()  # Monday=0 ... Sunday=6
    day_of_week = (day_of_week + 1) % 7   # convert to Sunday=0 ... Saturday=6, matching schema
    try:
        avail_res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/provider_availability"
            f"?day_of_week=eq.{day_of_week}&active=eq.true&select=start_time,end_time",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        windows = avail_res.json()
    except (httpx.RequestError, ValueError) as e:
        logger.error("get_available_slots: availability lookup failed: %s", e)
        return {"success": False, "error": "Could not load availability."}

    if not windows:
        return {"success": True, "slots": []}  # no working hours that day — e.g. day off

    # 3. Check for a full-day block (holiday, day off)
    try:
        block_res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/blocked_times?block_date=eq.{target_date}"
            f"&select=full_day,start_time,end_time",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        blocks = block_res.json()
    except (httpx.RequestError, ValueError) as e:
        logger.error("get_available_slots: blocked_times lookup failed: %s", e)
        return {"success": False, "error": "Could not load blocked times."}

    if any(b["full_day"] for b in blocks):
        return {"success": True, "slots": []}

    partial_blocks = [
        (_parse_time(b["start_time"]), _parse_time(b["end_time"]))
        for b in blocks if not b["full_day"] and b["start_time"] and b["end_time"]
    ]

    # 4. Get existing confirmed appointments that day
    try:
        appt_res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/appointments?appointment_date=eq.{target_date}"
            f"&status=eq.confirmed&select=start_time,end_time",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        booked = [
            (_parse_time(a["start_time"]), _parse_time(a["end_time"]))
            for a in appt_res.json()
        ]
    except (httpx.RequestError, ValueError) as e:
        logger.error("get_available_slots: appointments lookup failed: %s", e)
        return {"success": False, "error": "Could not load existing appointments."}

    occupied = partial_blocks + booked

    # 5. Generate candidate start times within each working window, at SLOT_STEP_MINUTES
    #    granularity, and keep only those where [start, start+duration) doesn't overlap
    #    anything already occupied, and don't run past closing time.
    slots = []
    for window_start, window_end in windows:
        w_start = _parse_time(window_start) if isinstance(window_start, str) else window_start
        w_end = _parse_time(window_end) if isinstance(window_end, str) else window_end

        cursor = datetime.combine(parsed_date, w_start)
        window_close = datetime.combine(parsed_date, w_end)

        while cursor + duration <= window_close:
            candidate_start = cursor.time()
            candidate_end = (cursor + duration).time()

            overlaps = any(
                candidate_start < occ_end and candidate_end > occ_start
                for occ_start, occ_end in occupied
            )

            # Don't offer slots in the past for today's date
            is_past = parsed_date == date_cls.today() and cursor < datetime.now()

            if not overlaps and not is_past:
                slots.append(candidate_start.strftime("%H:%M"))

            cursor += timedelta(minutes=SLOT_STEP_MINUTES)

    return {"success": True, "slots": slots}


# ── APPOINTMENTS (customer-facing) ───────────────────────────────────

def create_appointment(user_id: str, service_id: str, target_date: str,
                        start_time_str: str, notes: str = "") -> dict:
    """Books an appointment, re-checking availability at the moment of booking
    to avoid a race condition between two customers grabbing the same slot."""
    slots_result = get_available_slots(service_id, target_date)
    if not slots_result["success"]:
        return slots_result

    if start_time_str not in slots_result["slots"]:
        return {"success": False, "error": "That time is no longer available. Please pick another slot."}

    try:
        svc_res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/services?id=eq.{service_id}&select=duration_minutes",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        duration_minutes = svc_res.json()[0]["duration_minutes"]
    except (httpx.RequestError, ValueError, IndexError) as e:
        logger.error("create_appointment: service lookup failed: %s", e)
        return {"success": False, "error": "Could not verify service."}

    start_dt = datetime.strptime(start_time_str, "%H:%M")
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    try:
        res = httpx.post(
            f"{SUPABASE_URL}/rest/v1/appointments",
            headers={**HEADERS, "Prefer": "return=representation"},
            json={
                "user_id": user_id,
                "service_id": service_id,
                "appointment_date": target_date,
                "start_time": start_dt.strftime("%H:%M:%S"),
                "end_time": end_dt.strftime("%H:%M:%S"),
                "status": "confirmed",
                "notes": notes,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code >= 400:
            logger.error("create_appointment insert failed: %s", res.text)
            return {"success": False, "error": "Could not create appointment."}
        return {"success": True, "appointment": res.json()[0]}
    except (httpx.RequestError, IndexError) as e:
        logger.error("create_appointment failed: %s", e)
        return {"success": False, "error": "Could not create appointment."}


def get_user_appointments(user_id: str) -> dict:
    try:
        res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/appointments"
            f"?user_id=eq.{user_id}&order=appointment_date.desc,start_time.desc"
            f"&select=*,services(name,price,duration_minutes)",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        if res.status_code >= 400:
            return {"success": False, "error": "Could not load appointments."}
        return {"success": True, "appointments": res.json()}
    except httpx.RequestError as e:
        logger.error("get_user_appointments failed: %s", e)
        return {"success": False, "error": "Could not reach the database."}


def cancel_appointment(user_id: str, appointment_id: str) -> dict:
    try:
        # Confirm this appointment actually belongs to the requesting user before cancelling.
        check_res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/appointments?id=eq.{appointment_id}&select=user_id",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        check_data = check_res.json()
        if not check_data:
            return {"success": False, "error": "Appointment not found."}
        if check_data[0]["user_id"] != user_id and not _is_admin(user_id):
            return {"success": False, "error": "Not authorized to cancel this appointment."}

        res = httpx.patch(
            f"{SUPABASE_URL}/rest/v1/appointments?id=eq.{appointment_id}",
            headers=HEADERS,
            json={"status": "cancelled"},
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code >= 400:
            return {"success": False, "error": "Could not cancel appointment."}
        return {"success": True}
    except (httpx.RequestError, ValueError, IndexError) as e:
        logger.error("cancel_appointment failed: %s", e)
        return {"success": False, "error": "Could not cancel appointment."}


def admin_get_all_appointments(admin_user_id: str, from_date: str = None) -> dict:
    if not _is_admin(admin_user_id):
        return {"success": False, "error": "Not authorized."}
    try:
        url = (f"{SUPABASE_URL}/rest/v1/appointments?status=eq.confirmed"
               f"&order=appointment_date.asc,start_time.asc"
               f"&select=*,services(name,price,duration_minutes),profiles(name,email,phone_number)")
        if from_date:
            url += f"&appointment_date=gte.{from_date}"
        res = httpx.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if res.status_code >= 400:
            return {"success": False, "error": "Could not load appointments."}
        return {"success": True, "appointments": res.json()}
    except httpx.RequestError as e:
        logger.error("admin_get_all_appointments failed: %s", e)
        return {"success": False, "error": "Could not reach the database."}