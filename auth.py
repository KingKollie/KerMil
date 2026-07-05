import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")

supabase: Client = create_client(url, key)

def sign_up(name, age, email, phone_number, password):
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "name": name,
                    "age": age,
                    "phone_number": phone_number
                }
            }
        })

        user_id = response.user.id

        supabase.table("profiles").insert({
            "id": user_id,
            "name": name,
            "age": age,
            "email": email,
            "phone_number": phone_number
        }).execute()

        return {"success": True, "user_id": user_id, "name": name}

    except Exception as e:
        return {"success": False, "error": str(e)}


def sign_in(email, password):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        user_id = response.user.id

        profile = supabase.table("profiles").select("*").eq("id", user_id).execute()
        name = profile.data[0]["name"]

        return {"success": True, "user_id": user_id, "name": name}

    except Exception as e:
        return {"success": False, "error": str(e)}