from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from recommender import get_recommendation
from auth import sign_up, sign_in
from booking import (
    get_services, admin_create_service, admin_update_service, admin_delete_service,
    admin_set_weekly_availability, admin_block_time, get_available_slots,
    create_appointment, get_user_appointments, cancel_appointment, admin_get_all_appointments
)
import os
import base64
from anthropic import Anthropic

load_dotenv()

app = FastAPI(
    title="KerMil Skin Care & Hair API",
    description="AI-powered skin and hair care recommendations for the Black community",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── MODELS ──
class Profile(BaseModel):
    name: str
    gender: str
    hair_type: str
    hair_concerns: str
    skin_type: str
    skin_concerns: str
    budget: str

class SignUpRequest(BaseModel):
    name: str
    age: int
    email: str
    phone_number: str
    password: str

class SignInRequest(BaseModel):
    email: str
    password: str

class ServiceCreate(BaseModel):
    admin_user_id: str
    name: str
    description: str = ""
    duration_minutes: int
    price: float
    category: str = ""

class ServiceUpdate(BaseModel):
    admin_user_id: str
    updates: dict

class AvailabilitySet(BaseModel):
    admin_user_id: str
    day_of_week: int  # 0=Sunday ... 6=Saturday
    start_time: str    # "09:00"
    end_time: str      # "18:00"

class BlockTime(BaseModel):
    admin_user_id: str
    block_date: str    # "2026-08-01"
    full_day: bool = True
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    reason: str = ""

class AppointmentCreate(BaseModel):
    user_id: str
    service_id: str
    appointment_date: str  # "2026-08-01"
    start_time: str         # "14:30"
    notes: str = ""

class AppointmentCancel(BaseModel):
    user_id: str
    appointment_id: str

class PhotoAnalysisRequest(BaseModel):
    photo_base64: str
    routine_type: str  # "hair" or "skin"
    hair_type: str = ""
    hair_concerns: str = ""
    skin_type: str = ""
    skin_concerns: str = ""
    budget: str = ""


# ── AUTH ENDPOINTS ──
@app.post("/signup")
def signup(request: SignUpRequest):
    result = sign_up(
        request.name,
        request.age,
        request.email,
        request.phone_number,
        request.password
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/signin")
def signin(request: SignInRequest):
    result = sign_in(request.email, request.password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── RECOMMENDATION ENDPOINT ──
@app.post("/recommend")
def recommend(profile: Profile):
    result = get_recommendation(profile.dict())
    return {"recommendation": result}

@app.get("/health")
def health():
    return {"status": "healthy"}


# ── PHOTO ANALYSIS ──
@app.post("/analyze-photo")
def analyze_photo(request: PhotoAnalysisRequest):
    try:
        client = Anthropic()

        # Build the prompt based on routine type
        if request.routine_type == "hair":
            prompt = f"""You are a dermatologist and hair expert specializing in Black hair care.

Analyze this hair photo and provide:
1. Current hair condition assessment (dryness, damage, health)
2. Hair type confirmation (natural, relaxed, locs, etc.)
3. Specific concerns visible in the photo
4. A personalized 3-month daily & weekly hair care routine
5. Budget-friendly product recommendations with estimated prices
6. Pro tips specific to what you see in the photo

Hair Type: {request.hair_type}
Hair Concerns: {request.hair_concerns}
Budget: {request.budget}

Focus on products that work well for Black hair and are budget-friendly (under $20 per product)."""

        else:  # skin
            prompt = f"""You are a dermatologist specializing in Black skin care.

Analyze this skin photo and provide:
1. Current skin condition assessment (tone, texture, concerns)
2. Skin type confirmation (oily, dry, combination, etc.)
3. Specific skin concerns visible in the photo
4. A personalized 3-month daily & weekly skin care routine
5. Budget-friendly product recommendations with estimated prices
6. Pro tips specific to what you see in the photo

Skin Type: {request.skin_type}
Skin Concerns: {request.skin_concerns}
Budget: {request.budget}

Focus on products that work well for Black skin and are budget-friendly (under $20 per product)."""

        # Call Claude Vision with the image
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": request.photo_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        analysis = response.content[0].text

        return {
            "success": True,
            "analysis": analysis,
            "routine_type": request.routine_type
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ── BOOKING: CUSTOMER-FACING ENDPOINTS ──
@app.get("/services")
def list_services():
    result = get_services()
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/availability")
def check_availability(service_id: str, appointment_date: str):
    result = get_available_slots(service_id, appointment_date)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/appointments")
def book_appointment(request: AppointmentCreate):
    result = create_appointment(
        request.user_id, request.service_id, request.appointment_date,
        request.start_time, request.notes
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/appointments/{user_id}")
def my_appointments(user_id: str):
    result = get_user_appointments(user_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/appointments/cancel")
def cancel_my_appointment(request: AppointmentCancel):
    result = cancel_appointment(request.user_id, request.appointment_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── BOOKING: ADMIN-ONLY ENDPOINTS (require is_admin=true on the caller's profile) ──
@app.post("/admin/services")
def create_service(request: ServiceCreate):
    result = admin_create_service(
        request.admin_user_id, request.name, request.description,
        request.duration_minutes, request.price, request.category
    )
    if not result["success"]:
        raise HTTPException(status_code=403 if "authorized" in result["error"] else 400, detail=result["error"])
    return result

@app.patch("/admin/services/{service_id}")
def update_service(service_id: str, request: ServiceUpdate):
    result = admin_update_service(request.admin_user_id, service_id, request.updates)
    if not result["success"]:
        raise HTTPException(status_code=403 if "authorized" in result["error"] else 400, detail=result["error"])
    return result

@app.delete("/admin/services/{service_id}")
def delete_service(service_id: str, admin_user_id: str):
    result = admin_delete_service(admin_user_id, service_id)
    if not result["success"]:
        raise HTTPException(status_code=403 if "authorized" in result["error"] else 400, detail=result["error"])
    return result

@app.post("/admin/availability")
def set_availability(request: AvailabilitySet):
    result = admin_set_weekly_availability(
        request.admin_user_id, request.day_of_week, request.start_time, request.end_time
    )
    if not result["success"]:
        raise HTTPException(status_code=403 if "authorized" in result["error"] else 400, detail=result["error"])
    return result

@app.post("/admin/block-time")
def block_time(request: BlockTime):
    result = admin_block_time(
        request.admin_user_id, request.block_date, request.full_day,
        request.start_time, request.end_time, request.reason
    )
    if not result["success"]:
        raise HTTPException(status_code=403 if "authorized" in result["error"] else 400, detail=result["error"])
    return result

@app.get("/admin/appointments")
def all_appointments(admin_user_id: str, from_date: Optional[str] = None):
    result = admin_get_all_appointments(admin_user_id, from_date)
    if not result["success"]:
        raise HTTPException(status_code=403 if "authorized" in result["error"] else 400, detail=result["error"])
    return result


app.mount("/", StaticFiles(directory=".", html=True), name="static")