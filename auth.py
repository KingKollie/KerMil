import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def sign_up(name, age, email, phone_number, password):
    try:
        # Create auth user
        res = httpx.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers=HEADERS,
            json={"email": email, "password": password}
        )
        data = res.json()
        if "error" in data and data["error"]:
            return {"success": False, "error": data.get("msg", "Signup failed")}

        user_id = data["user"]["id"]

        # Save profile
        httpx.post(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers={**HEADERS, "Prefer": "return=minimal"},
            json={
                "id": user_id,
                "name": name,
                "age": age,
                "email": email,
                "phone_number": phone_number
            }
        )

        return {"success": True, "user_id": user_id, "name": name}

    except Exception as e:
        return {"success": False, "error": str(e)}


def sign_in(email, password):
    try:
        res = httpx.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers=HEADERS,
            json={"email": email, "password": password}
        )
        data = res.json()

        if "error" in data:
            return {"success": False, "error": data.get("error_description", "Sign in failed")}

        access_token = data["access_token"]
        user = data.get("user") or data.get("session", {}).get("user")
        if not user:
            return {"success": False, "error": "Account may already exist. Try signing in."}
        user_id = data["user"]["id"]

        # Get profile
        profile_res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}&select=*",
            headers={**HEADERS, "Authorization": f"Bearer {access_token}"}
        )
        profile_data = profile_res.json()
        name = profile_data[0]["name"] if profile_data else "Friend"

        return {"success": True, "user_id": user_id, "name": name}

    except Exception as e:
        return {"success": False, "error": str(e)}