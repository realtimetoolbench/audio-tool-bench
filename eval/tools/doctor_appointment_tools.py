"""
Doctor appointment tools
"""
from typing import Dict, Any
import random
import string

from .base import Tool
from .mock_data import DOCTORS


def _find_doctor_by_id(doctor_id: str):
    """Find doctor by doctor_id across all cities"""
    for city_doctors in DOCTORS.values():
        for doctor in city_doctors:
            if doctor.get("doctor_id") == doctor_id:
                return doctor
    return None


class DoctorSearchTool(Tool):
    """Doctor search tool"""

    def __init__(self):
        self.doctors = DOCTORS

    @property
    def name(self) -> str:
        return "search_doctors"

    @property
    def description(self) -> str:
        return "Search for doctors by city, hospital, department, and specialty."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name (e.g., Beijing, Shanghai, Chengdu)"},
                "department": {"type": "string", "description": "Department (Internal Medicine, Surgery, Pediatrics, Neurology, etc.)"}
            },
            "required": ["city"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        city = kwargs.get("city")
        hospital = kwargs.get("hospital")
        department = kwargs.get("department")
        doctor_name = kwargs.get("doctor_name")
        specialty = kwargs.get("specialty")
        date = kwargs.get("date")

        if city not in self.doctors:
            return {
                "success": False,
                "error": f"City not supported: {city}",
                "available_cities": list(self.doctors.keys())
            }

        results = self.doctors[city].copy()

        if hospital:
            results = [d for d in results if hospital.lower() in d["hospital"].lower()]
        if department:
            results = [d for d in results if department.lower() in d["department"].lower()]
        if doctor_name:
            results = [d for d in results if doctor_name.lower() in d["name"].lower()]
        if specialty:
            results = [d for d in results if specialty.lower() in d["specialty"].lower()]
        if date:
            results = [d for d in results if date in d["available_dates"]]

        if not results:
            output = f"No doctors found in {city} matching criteria."
        else:
            output = f"Found {len(results)} doctors in {city}:\n\n"
            for i, d in enumerate(results, 1):
                output += f"{i}. Dr. {d['name']} (ID: {d['doctor_id']})\n"
                output += f"   Hospital: {d['hospital']}\n"
                output += f"   Department: {d['department']}\n"
                output += f"   Specialty: {d['specialty']}\n"
                output += f"   Title: {d['title']}\n"
                output += f"   Rating: {d['rating']}/5.0\n"
                output += f"   Experience: {d['experience_years']} years\n"
                output += f"   Available: {', '.join(d['available_dates'])}\n\n"

        return {
            "success": True,
            "output": output,
            "raw_output": results,
            "error": None,
            "count": len(results),
            "doctors": results
        }


class BookAppointmentTool(Tool):
    """Doctor appointment booking tool"""

    def __init__(self):
        self.appointments = []

    @property
    def name(self) -> str:
        return "book_appointment"

    @property
    def description(self) -> str:
        return "Book a doctor appointment with doctor name, hospital, date, time slot, and patient info."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string", "description": "Doctor ID from search results (e.g., 'doc_bj_001')"},
                "date": {"type": "string", "description": "Appointment date (YYYY-MM-DD)"},
                "time_slot": {"type": "string", "description": "Time slot (morning, afternoon)", "enum": ["morning", "afternoon"]},
                "patient_name": {"type": "string", "description": "Patient name"}
                # TODO: optional 参数暂时禁用
                # "patient_phone": {"type": "string", "description": "Patient phone number"},
                # "id_number": {"type": "string", "description": "Patient ID number"},
                # "symptoms": {"type": "string", "description": "Symptom description (optional)"}
            },
            "required": ["doctor_id", "date", "time_slot", "patient_name"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        import time
        start_time = time.time()

        doctor_id = kwargs.get("doctor_id")

        # Look up doctor by ID
        doctor = _find_doctor_by_id(doctor_id)
        if not doctor:
            return {
                "success": False,
                "output": f"Doctor not found: {doctor_id}. Please search for doctors first.",
                "raw_output": None,
                "error": f"Invalid doctor_id: {doctor_id}",
                "latency_ms": (time.time() - start_time) * 1000
            }

        doctor_name = doctor["name"]
        hospital = doctor["hospital"]
        department = doctor["department"]

        appointment_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

        appointment = {
            "appointment_id": appointment_id,
            "doctor_id": doctor_id,
            "doctor_name": doctor_name,
            "hospital": hospital,
            "department": department,
            "date": kwargs.get("date"),
            "time_slot": kwargs.get("time_slot"),
            "patient_name": kwargs.get("patient_name"),
            "patient_phone": kwargs.get("patient_phone"),
            "id_number": kwargs.get("id_number"),
            "symptoms": kwargs.get("symptoms", "Not provided"),
            "status": "Confirmed",
            "queue_number": random.randint(1, 50)
        }

        self.appointments.append(appointment)

        output = f"Doctor appointment booked successfully!\n\n"
        output += f"Appointment ID: {appointment_id}\n"
        output += f"Doctor ID: {doctor_id}\n"
        output += f"Doctor: {doctor_name}\n"
        output += f"Hospital: {hospital}\n"
        output += f"Department: {department}\n"
        output += f"Date: {kwargs.get('date')}\n"
        output += f"Time slot: {kwargs.get('time_slot')}\n"
        output += f"Patient: {kwargs.get('patient_name')}\n"
        output += f"Queue number: {appointment['queue_number']}\n"
        output += f"Status: Confirmed\n"

        return {
            "success": True,
            "output": output,
            "raw_output": appointment,
            "error": None,
            "latency_ms": (time.time() - start_time) * 1000,
            "message": "Appointment booked successfully",
            "appointment": appointment
        }
