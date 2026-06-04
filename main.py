from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv
from pydantic import BaseModel
from twilio.rest import Client
import os

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://laurelsoars-sys.github.io",
        "http://127.0.0.1:5500",
        "*"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "PUT", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"]
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

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
def get_sessions(limit: int = 5, offset: int = 0, filter: str = "upcoming"):
    from datetime import date
    today = date.today().isoformat()
    result = supabase.table("sessions").select("*").order("date").execute()
    all_sessions = result.data
    
    if filter == "upcoming":
        filtered = [s for s in all_sessions if s["date"] >= today]
    else:
        filtered = [s for s in all_sessions if s["date"] < today]
    
    return filtered[offset:offset+limit]

class Session(BaseModel):
    date: str
    time: str
    expected_kids: int
    created_by: str
    notes: str = ""

@app.post("/sessions")
def create_session(session: Session):
    result = supabase.table("sessions").insert({
        "date": session.date,
        "time": session.time,
        "expected_kids": session.expected_kids,
        "created_by": session.created_by,
        "notes": session.notes
    }).execute()
    return result.data

@app.get("/availability/{session_id}")
def get_availability(session_id: str):
    result = supabase.table("availability").select("*").filter("session_id", "eq", session_id).execute()
    availability = result.data
    
    if len(availability) == 0:
        return availability
    
    helper_ids = [record["helper_id"] for record in availability]
    profiles = supabase.table("profiles").select("id, full_name").execute()
    profile_map = {p["id"]: p["full_name"] for p in profiles.data}
    
    for record in availability:
        record["helper_name"] = profile_map.get(record["helper_id"], "Unknown helper")
    
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
@app.delete("/availability/{session_id}/{helper_id}")
def withdraw_availability(session_id: str, helper_id: str):
    result = supabase.table("availability").delete().filter("session_id", "eq", session_id).filter("helper_id", "eq", helper_id).execute()
    return {"message": "Withdrawn successfully"}

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    supabase.table("assignments").delete().filter("sessions_id", "eq", session_id).execute()
    supabase.table("availability").delete().filter("session_id", "eq", session_id).execute()
    supabase.table("sessions").delete().filter("id", "eq", session_id).execute()
    return {"message": "Session deleted successfully"}
class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: str

@app.post("/signup")
def signup(request: SignupRequest):
    try:
        result = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password
        })
        user = result.user
        supabase.table("profiles").insert({
            "id": user.id,
            "email": request.email,
            "full_name": request.full_name,
            "role": "helper",
            "phone": request.phone
        }).execute()
        return {"message": "Account created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
def send_sms(to_phone: str, message: str):
    try:
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=to_phone
        )
    except Exception as e:
        print(f"SMS failed: {e}")    
@app.get("/fairness")
def get_fairness():
    profiles = supabase.table("profiles").select("id, full_name").filter("role", "eq", "helper").execute()
    assignments = supabase.table("assignments").select("helper_id").execute()
    availability = supabase.table("availability").select("helper_id").execute()
    
    assignment_counts = {}
    for a in assignments.data:
        hid = a["helper_id"]
        assignment_counts[hid] = assignment_counts.get(hid, 0) + 1
    
    availability_counts = {}
    for a in availability.data:
        hid = a["helper_id"]
        availability_counts[hid] = availability_counts.get(hid, 0) + 1
    
    result = []
    for profile in profiles.data:
        pid = profile["id"]
        assigned = assignment_counts.get(pid, 0)
        available = availability_counts.get(pid, 0)
        rate = round((assigned / available) * 100) if available > 0 else 0
        result.append({
            "name": profile["full_name"],
            "sessions": assigned,
            "available": available,
            "rate": rate
        })
    
    result.sort(key=lambda x: x["rate"])
    return result
class AssignmentUpdate(BaseModel):
    status: str
@app.options("/assignments/{session_id}/{helper_id}")
def options_assignments(session_id: str, helper_id: str):
    return {}

@app.patch("/assignments/{session_id}/{helper_id}")
def update_assignment(session_id: str, helper_id: str, update: AssignmentUpdate):
    existing = supabase.table("assignments").select("*").filter("sessions_id", "eq", session_id).filter("helper_id", "eq", helper_id).execute()
    
    if len(existing.data) > 0:
        supabase.table("assignments").update({"status": update.status}).filter("sessions_id", "eq", session_id).filter("helper_id", "eq", helper_id).execute()
    else:
        supabase.table("assignments").insert({
            "sessions_id": session_id,
            "helper_id": helper_id,
            "approved_by": "coach",
            "status": update.status
        }).execute()

    if update.status in ["approved", "waitlist"]:
        session = supabase.table("sessions").select("date, time").filter("id", "eq", session_id).execute()
        profile = supabase.table("profiles").select("phone, full_name").filter("id", "eq", helper_id).execute()
        
        if session.data and profile.data and profile.data[0].get("phone"):
            date = session.data[0]["date"]
            time = session.data[0]["time"]
            name = profile.data[0]["full_name"]
            phone = profile.data[0]["phone"]
            
            if update.status == "approved":
                msg = f"Hi {name}! You've been approved for the tennis session on {date} at {time}. See you there!"
            else:
                msg = f"Hi {name}! You've been added to the waitlist for the tennis session on {date} at {time}."
            
            send_sms(phone, msg)

    return {"message": "Updated successfully"}
class SessionUpdate(BaseModel):
    date: str
    time: str
    expected_kids: int
    notes: str = ""

@app.patch("/sessions/{session_id}")
def update_session(session_id: str, update: SessionUpdate):
    supabase.table("sessions").update({
        "date": update.date,
        "time": update.time,
        "expected_kids": update.expected_kids,
        "notes": update.notes
    }).filter("id", "eq", session_id).execute()
    return {"message": "Session updated successfully"}

@app.options("/sessions/{session_id}")
def options_session(session_id: str):
    return {}
@app.patch("/sessions/{session_id}/cancel")
def cancel_session(session_id: str):
    supabase.table("sessions").update({"status": "cancelled"}).filter("id", "eq", session_id).execute()
    return {"message": "Session cancelled"}

@app.options("/sessions/{session_id}/cancel")
def options_cancel(session_id: str):
    return {}
class Attendance(BaseModel):
    session_id: str
    helper_id: str
    showed_up: bool = True
    notes: str = ""

@app.get("/attendance/{session_id}")
def get_attendance(session_id: str):
    result = supabase.table("attendance").select("*").filter("session_id", "eq", session_id).execute()
    return result.data

@app.post("/attendance")
def mark_attendance(attendance: Attendance):
    existing = supabase.table("attendance").select("*").filter("session_id", "eq", attendance.session_id).filter("helper_id", "eq", attendance.helper_id).execute()
    if len(existing.data) > 0:
        supabase.table("attendance").update({
            "showed_up": attendance.showed_up,
            "notes": attendance.notes
        }).filter("session_id", "eq", attendance.session_id).filter("helper_id", "eq", attendance.helper_id).execute()
    else:
        supabase.table("attendance").insert({
            "session_id": attendance.session_id,
            "helper_id": attendance.helper_id,
            "showed_up": attendance.showed_up,
            "notes": attendance.notes
        }).execute()
    return {"message": "Attendance recorded"}

@app.options("/attendance")
def options_attendance():
    return {}