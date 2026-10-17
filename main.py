from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
import requests
import os
from dotenv import load_dotenv

# 1. Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:////tmp/visa_slots.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Database Models (Tables)
class Slot(Base):
    __tablename__ = "slots"
    id = Column(Integer, primary_key=True, index=True)
    location = Column(String, index=True)
    date = Column(String)
    status = Column(String)

class Subscriber(Base):
    __tablename__ = "subscribers"
    id = Column(Integer, primary_key=True, index=True)
    telegram_chat_id = Column(String, unique=True, index=True)
    location = Column(String)

# Create tables
Base.metadata.create_all(bind=engine)

# 3. FastAPI App and Schemas
app = FastAPI()

class SlotCreate(BaseModel):
    location: str
    date: str
    status: str

class SubscriberCreate(BaseModel):
    telegram_chat_id: str
    location: str

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def send_telegram_alert(chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")
# 4. API Endpoints
@app.get("/")
def read_root():
    return {"message": "Visa Slot Backend is Running!"}

# Subscriber register (With Error Handling)
@app.post("/subscribe/")
def subscribe(subscriber: SubscriberCreate):
    db = SessionLocal()
    try:
        # Check if the user is already subscribed for this location
        existing_sub = db.query(Subscriber).filter(
            Subscriber.telegram_chat_id == subscriber.telegram_chat_id
        ).first()

        if existing_sub:
            return {"status": "info", "message": "Meeru already subscribe ayyaru!"}

        # If not, add new subscriber
        new_sub = Subscriber(telegram_chat_id=subscriber.telegram_chat_id, location=subscriber.location)
        db.add(new_sub)
        db.commit()
        return {"status": "success", "message": "Successfully Subscribed!"}
    
    except Exception as e:
        db.rollback() # Database error vaste changes ni revert chesthundi
        return {"status": "error", "message": f"Database Error: {str(e)}"}
    
    finally:
        db.close() # Enti jarigina database connection close avvali

# Chrome Extension nunchi Slot Data receive cheyadam (With Duplicate Check)
@app.post("/update-slot/")
def update_slot(slot: SlotCreate):
    db = SessionLocal()
    try:
        # Check if this exact slot already exists in DB
        existing_slot = db.query(Slot).filter(
            Slot.location == slot.location,
            Slot.date == slot.date
        ).first()

        if existing_slot:
            # If slot exists, just update the status (e.g., from 'Closed' to 'Open')
            existing_slot.status = slot.status
            db.commit()
            message = "Slot status updated in DB."
        else:
            # If it's a new slot, save it
            new_slot = Slot(location=slot.location, date=slot.date, status=slot.status)
            db.add(new_slot)
            db.commit()
            message = "New slot saved in DB."

        # Find subscribers for this location
        subscribers = db.query(Subscriber).filter(Subscriber.location == slot.location).all()
        
        # Send Telegram Alerts
        for sub in subscribers:
            msg = f"🚨 SLOT ALERT! 🚨\nLocation: {slot.location}\nDate: {slot.date}\nStatus: {slot.status}"
            send_telegram_alert(sub.telegram_chat_id, msg)
        
        return {"status": "success", "message": f"{message} Alerts sent to {len(subscribers)} users!"}
    
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error updating slot: {str(e)}"}
    
    finally:
        db.close() 
       


