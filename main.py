import os
from datetime import datetime, date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr

from database import db, create_document, get_documents

app = FastAPI(title="Bus Booking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------
# Utils
# ------------------------------------

def serialize_doc(doc: dict):
    from bson import ObjectId
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

# ------------------------------------
# Schemas (request models)
# ------------------------------------

class SearchTripsQuery(BaseModel):
    origin: str
    destination: str
    travel_date: date

class BookingRequest(BaseModel):
    trip_id: str = Field(..., description="Trip id to book")
    full_name: str
    email: EmailStr
    phone: str
    seats: int = Field(..., ge=1, le=10)

# ------------------------------------
# Basic endpoints
# ------------------------------------

@app.get("/")
def read_root():
    return {"message": "Bus Booking API is running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

# ------------------------------------
# Domain: Bus Routes, Trips, Bookings
# ------------------------------------

@app.post("/api/seed")
def seed_sample_data():
    """Seed a few sample routes and trips if none exist"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    has_trips = db["trip"].count_documents({}) > 0
    if has_trips:
        return {"status": "ok", "message": "Trips already seeded"}

    # Create routes
    route_ny_bos = {
        "origin": "New York",
        "destination": "Boston",
        "duration_minutes": 240,
    }
    route_sf_la = {
        "origin": "San Francisco",
        "destination": "Los Angeles",
        "duration_minutes": 420,
    }
    r1_id = create_document("busroute", route_ny_bos)
    r2_id = create_document("busroute", route_sf_la)

    # Create trips for today and tomorrow
    today = date.today()
    tomorrow = date.fromordinal(today.toordinal() + 1)

    sample_trips = [
        {"route_id": r1_id, "travel_date": today.isoformat(), "departure_time": "08:00", "bus_company": "SwiftBus", "price": 39.99, "capacity": 40},
        {"route_id": r1_id, "travel_date": today.isoformat(), "departure_time": "17:30", "bus_company": "MetroLines", "price": 44.50, "capacity": 50},
        {"route_id": r2_id, "travel_date": tomorrow.isoformat(), "departure_time": "07:15", "bus_company": "Pacific Coaches", "price": 59.00, "capacity": 45},
        {"route_id": r2_id, "travel_date": tomorrow.isoformat(), "departure_time": "18:45", "bus_company": "GoldenGate Bus", "price": 62.50, "capacity": 40},
    ]

    for t in sample_trips:
        create_document("trip", t)

    return {"status": "ok", "message": "Seeded sample trips"}

@app.get("/api/trips/search")
def search_trips(origin: str = Query(...), destination: str = Query(...), travel_date: date = Query(...)):
    """Find trips for given route and date"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Find routes matching origin/destination
    routes = get_documents("busroute", {"origin": {"$regex": f"^{origin}$", "$options": "i"}, "destination": {"$regex": f"^{destination}$", "$options": "i"}})
    route_ids = [str(r["_id"]) for r in routes]
    if not route_ids:
        return {"trips": []}

    # Find trips on that date
    trips = get_documents("trip", {"route_id": {"$in": route_ids}, "travel_date": travel_date.isoformat()})

    # Attach route info and availability
    results = []
    for trip in trips:
        trip_id = str(trip["_id"])
        bookings = get_documents("booking", {"trip_id": trip_id})
        seats_booked = sum(int(b.get("seats", 0)) for b in bookings)
        available = max(0, int(trip.get("capacity", 0)) - seats_booked)

        # find route for names
        route = next((r for r in routes if str(r["_id"]) == trip.get("route_id")), None)
        item = serialize_doc(trip)
        item["available_seats"] = available
        if route:
            item["origin"] = route.get("origin")
            item["destination"] = route.get("destination")
            item["duration_minutes"] = route.get("duration_minutes")
        results.append(item)

    return {"trips": results}

@app.post("/api/book")
def book_trip(payload: BookingRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Get trip
    from bson import ObjectId
    try:
        trip_obj = db["trip"].find_one({"_id": ObjectId(payload.trip_id)})
    except Exception:
        trip_obj = None
    if not trip_obj:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Check availability
    bookings = get_documents("booking", {"trip_id": payload.trip_id})
    seats_booked = sum(int(b.get("seats", 0)) for b in bookings)
    available = max(0, int(trip_obj.get("capacity", 0)) - seats_booked)
    if payload.seats > available:
        raise HTTPException(status_code=400, detail=f"Only {available} seats available")

    booking_id = create_document("booking", payload.model_dump())
    return {"status": "confirmed", "booking_id": booking_id}

@app.get("/api/bookings")
def list_bookings(email: Optional[str] = None):
    filt = {"email": email} if email else {}
    docs = get_documents("booking", filt)
    return {"bookings": [serialize_doc(d) for d in docs]}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
