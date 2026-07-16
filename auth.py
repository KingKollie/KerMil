"""
KerMil authentication module — Supabase-backed sign up / sign in.

Every public function returns a consistent shape:
    {"success": True,  "user_id": ..., "name": ...}
    {"success": False, "error": "<human-readable message>"}

Never returns None. Never lets an unexpected exception escape uncaught.
"""

import os
import re
import logging
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("kermil.auth")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

# Fail fast and loud at import time if config is missing, instead of every
# request silently sending "Authorization: Bearer None" to Supabase.
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing required environment variables: SUPABASE_URL and/or "
        "SUPABASE_ANON_KEY. Check your .env file / Render environment settings."
    )

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

REQUEST_TIMEOUT = 10.0  # seconds — prevents a hung Supabase call from hanging your API forever

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_signup_fields(name: str, age, email: str, phone_number: str, password: str) -> Optional[str]:
    """Returns an error string if invalid, else None."""
    if not name or not name.strip():
        return "Name is required."
    if not email or not _EMAIL_RE.match(email):
        return "A valid email address is required."
    if not password or len(password) < 8:
        return "Password must be at least 8 characters."
    if age is not None:
        try:
            age_int = int(age)
            if age_int < 13 or age_int > 120:
                return "Age must be between 13 and 120."
        except (ValueError, TypeError):
            return "Age must be a number."
    return None


def sign_up(name: str, age, email: str, phone_number: str, password: str) -> dict:
    """
    Create a new Supabase auth user and a matching row in `profiles`.
    Always returns a dict — never None — so callers can safely do result["success"].
    """
    validation_error = _validate_signup_fields(name, age, email, phone_number, password)
    if validation_error:
        return {"success": False, "error": validation_error}

    try:
        res = httpx.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers=HEADERS,
            json={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.RequestError as e:
        logger.error("Signup request failed to reach Supabase: %s", e)
        return {"success": False, "error": "Could not reach the authentication service. Please try again."}

    try:
        data = res.json()
    except ValueError:
        logger.error("Signup response was not valid JSON. status=%s body=%r", res.status_code, res.text)
        return {"success": False, "error": "Unexpected response from authentication service."}

    # Supabase returns HTTP 200 with an error-shaped body in some cases (not just 4xx),
    # so status code alone isn't a reliable success signal — check the body too.
    if res.status_code >= 400:
        message = data.get("msg") or data.get("error_description") or data.get("error") or "Signup failed."
        logger.info("Signup rejected by Supabase (status=%s): %s", res.status_code, message)
        return {"success": False, "error": message}

    user = data.get("user")

    # Supabase's quirky duplicate-email behavior: sometimes returns 200 with a user
    # object that has an empty "identities" list instead of an error, when the email
    # is already registered. Catch that explicitly with a clear message.
    if user and isinstance(user.get("identities"), list) and len(user["identities"]) == 0:
        return {"success": False, "error": "An account with this email already exists. Try signing in instead."}

    if not user or "id" not in user:
        logger.error("Signup succeeded per Supabase but response had no user.id: %r", data)
        return {"success": False, "error": "Signup did not complete correctly. Please try again."}

    user_id = user["id"]

    # Save profile. If this fails, the auth user still exists — log it clearly so it's
    # debuggable, but don't claim signup failed when the account was actually created.
    try:
        profile_res = httpx.post(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers={**HEADERS, "Prefer": "return=minimal"},
            json={
                "id": user_id,
                "name": name,
                "age": age,
                "email": email,
                "phone_number": phone_number,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if profile_res.status_code >= 400:
            logger.error(
                "Profile insert failed for user_id=%s (status=%s): %s",
                user_id, profile_res.status_code, profile_res.text,
            )
    except httpx.RequestError as e:
        logger.error("Profile insert request failed for user_id=%s: %s", user_id, e)

    return {"success": True, "user_id": user_id, "name": name}


def sign_in(email: str, password: str) -> dict:
    """
    Authenticate against Supabase and return the user's id + display name.
    Always returns a dict — never None.
    """
    if not email or not password:
        return {"success": False, "error": "Email and password are required."}

    try:
        res = httpx.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers=HEADERS,
            json={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.RequestError as e:
        logger.error("Sign-in request failed to reach Supabase: %s", e)
        return {"success": False, "error": "Could not reach the authentication service. Please try again."}

    try:
        data = res.json()
    except ValueError:
        logger.error("Sign-in response was not valid JSON. status=%s body=%r", res.status_code, res.text)
        return {"success": False, "error": "Unexpected response from authentication service."}

    if res.status_code >= 400 or "error" in data:
        message = data.get("error_description") or data.get("msg") or data.get("error") or "Sign in failed."
        return {"success": False, "error": message}

    access_token = data.get("access_token")
    user = data.get("user")
    if not access_token or not user or "id" not in user:
        logger.error("Sign-in response missing access_token/user.id: %r", data)
        return {"success": False, "error": "Sign in did not complete correctly. Please try again."}

    user_id = user["id"]
    name = user.get("user_metadata", {}).get("name", "")

    if not name:
        try:
            profile_res = httpx.get(
                f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}&select=*",
                headers={**HEADERS, "Authorization": f"Bearer {access_token}"},
                timeout=REQUEST_TIMEOUT,
            )
            profile_data = profile_res.json()
            if isinstance(profile_data, list) and len(profile_data) > 0:
                name = profile_data[0].get("name", "Friend")
            else:
                name = email.split("@")[0]
        except (httpx.RequestError, ValueError) as e:
            logger.warning("Could not fetch profile for user_id=%s: %s", user_id, e)
            name = email.split("@")[0]

    return {"success": True, "user_id": user_id, "name": name, "access_token": access_token}