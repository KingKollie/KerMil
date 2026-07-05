from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

def sign_up(name, age, email, phone_number, password):
    try:
        # Create auth account
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
       
        user_id = response.user.id
       
        # Save profile to profiles table
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
       
        # Get their profile
        profile = supabase.table("profiles").select("*").eq("id", user_id).execute()
        name = profile.data[0]["name"]
       
        return {"success": True, "user_id": user_id, "name": name}
   
    except Exception as e:
        return {"success": False, "error": str(e)}


def sign_out(jwt):
    try:
        supabase.auth.sign_out()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}