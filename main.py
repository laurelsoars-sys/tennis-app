from fastapi import FastAPI
from supabase import create_client
from dotenv import load_dotenv
from pydantic import BaseModel
import os

load_dotenv()

app = FastAPI()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

class Session(BaseModel):
    date: str
    time: str
    expected_kids: int
    created_by: str

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
class Availability(BaseModel):
    session_id: str
    helper_id: str
    status: str

@app.get("/availability/{session_id}")
def get_availability(session_id: str):
    result = supabase.table("availability").select("*").filter("session_id", "eq", session_id).execute()
    return result.data

@app.post("/availability")
def mark_availability(availability: Availability):
    result = supabase.table("availability").insert({
        "session_id": availability.session_id,
        "helper_id": availability.helper_id,
        "status": availability.status
    }).execute()
    return result.data
class Assignment(BaseModel):
    session_id: str
    helper_id: str
    approved_by: str

@app.get("/assignments/{session_id}")
def get_assignments(session_id: str):
    result = supabase.table("assignments").select("*").filter("session_id", "eq", session_id).execute()
    return result.data

@app.post("/assignments")
def create_assignment(assignment: Assignment):
    result = supabase.table("assignments").insert({
        "sessions_id": assignment.session_id,
        "helper_id": assignment.helper_id,
        "approved_by": assignment.approved_by
    }).execute()
    return result.data