from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from recommender import get_recommendation
from auth import sign_up, sign_in
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

class PhotoAnalysisRequest(BaseModel):
    photo_base64: str
    routine_type: str  # "hair" or "skin"
    hair_type: str = ""
    hair_concerns: str = ""
    skin_type: str = ""
    skin_concerns: str = ""
    budget: str = ""

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

app.mount("/", StaticFiles(directory=".", html=True), name="static")
