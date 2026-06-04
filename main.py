from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv
from pydantic import BaseModel
import os

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


class Session(BaseModel):
    date: str
    time: str
    expected_kids: int
    created_by: str

class Availability(BaseModel):
    session_id: str
    helper_id: str
    status: str

class Assignment(BaseModel):
    session_id: str
    helper_id: str
    approved_by: str

class LoginRequest(BaseModel):
    email: str
    password: str

@app.get("/")
def home():
    return {"message": "Tennis app is running!"}

@app.get("/sessions")
def get_sessions():
    result = supabase.table("sessions").select("*").execute()
    return result.data

@app.post("/sessions")
def create_session(session: Session):
    result = supabase.table("sessions").insert({
        "date": session.date,
        "time": session.time,
        "expected_kids": session.expected_kids,
        "created_by": session.created_by
    }).execute()
    return result.data

@app.get("/availability/{session_id}")
def get_availability(session_id: str):
    result = supabase.table("availability").select("*").filter("session_id", "eq", session_id).execute()
    availability = result.data
    for record in availability:
        profile = supabase.table("profiles").select("full_name").filter("id", "eq", record["helper_id"]).execute()
        if len(profile.data) > 0:
            record["helper_name"] = profile.data[0]["full_name"]
        else:
            record["helper_name"] = "Unknown helper"
    return availability

@app.post("/availability")
def mark_availability(availability: Availability):
    result = supabase.table("availability").insert({
        "session_id": availability.session_id,
        "helper_id": availability.helper_id,
        "status": availability.status
    }).execute()
    return result.data

@app.get("/assignments/{session_id}")
def get_assignments(session_id: str):
    result = supabase.table("assignments").select("*").filter("sessions_id", "eq", session_id).execute()
    return result.data

@app.post("/assignments")
def create_assignment(assignment: Assignment):
    result = supabase.table("assignments").insert({
        "sessions_id": assignment.session_id,
        "helper_id": assignment.helper_id,
        "approved_by": assignment.approved_by
    }).execute()
    return result.data

@app.post("/login")
def login(request: LoginRequest):
    result = supabase.auth.sign_in_with_password({
        "email": request.email,
        "password": request.password
    })
    user = result.user
    profile = supabase.table("profiles").select("*").filter("email", "eq", request.email).execute()
    if len(profile.data) == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {
        "id": user.id,
        "email": user.email,
        "role": profile.data[0]["role"],
        "full_name": profile.data[0]["full_name"]
    }