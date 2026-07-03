from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from recommender import get_recommendation
import os

load_dotenv()

app = FastAPI(
    title="KerMil Skin Care & Hair API",
    description="AI-powered skin and hair care recommendations for the Black community",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Profile(BaseModel):
    name: str
    gender: str
    hair_type: str
    hair_concerns: str
    skin_type: str
    skin_concerns: str
    budget: str

@app.post("/recommend")
def recommend(profile: Profile):
    result = get_recommendation(profile.dict())
    return {"recommendation": result}

@app.get("/health")
def health():
    return {"status": "healthy"}

app.mount("/", StaticFiles(directory=".", html=True), name="static")