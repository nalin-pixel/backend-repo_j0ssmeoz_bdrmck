"""
Database Schemas for Bus Booking App

Each Pydantic model represents a MongoDB collection.
Collection name equals the lowercase class name.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import date

class Busroute(BaseModel):
    """
    Bus routes between cities
    Collection: "busroute"
    """
    origin: str = Field(..., description="Starting city")
    destination: str = Field(..., description="Destination city")
    duration_minutes: int = Field(..., ge=1, description="Approx trip duration in minutes")

class Trip(BaseModel):
    """
    A scheduled trip for a bus route on a specific date/time
    Collection: "trip"
    """
    route_id: str = Field(..., description="ID of the busroute")
    travel_date: date = Field(..., description="Date of travel (YYYY-MM-DD)")
    departure_time: str = Field(..., description="Departure time in 24h HH:MM")
    bus_company: str = Field(..., description="Operator/Company name")
    price: float = Field(..., ge=0, description="Price per seat")
    capacity: int = Field(..., ge=1, description="Total seats available on the bus")

class Booking(BaseModel):
    """
    A customer booking for a trip
    Collection: "booking"
    """
    trip_id: str = Field(..., description="ID of the trip being booked")
    full_name: str = Field(..., description="Passenger full name")
    email: EmailStr = Field(..., description="Contact email")
    phone: str = Field(..., description="Contact phone number")
    seats: int = Field(..., ge=1, le=10, description="Number of seats to book")
    status: str = Field("confirmed", description="Booking status")
