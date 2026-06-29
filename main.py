from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
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

@app.get("/")
def home():
    return {
        "app": "KerMil Skin Care & Hair",
        "version": "1.0.0",
        "message": "Welcome to KerMil API!"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}