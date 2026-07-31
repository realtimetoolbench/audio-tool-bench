"""
Civic and local public service tools
"""
from typing import Dict, Any
import random
import string

from .base import Tool
from .mock_data import SERVICE_CENTERS, CIVIC_APPLICATIONS


def _find_center(center_id: str):
    for center in SERVICE_CENTERS:
        if center["center_id"] == center_id:
            return center
    return None


class ServiceCenterSearchTool(Tool):
    @property
    def name(self) -> str:
        return "search_service_centers"

    @property
    def description(self) -> str:
        return "Search civic service centers by city and service type."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "service_type": {"type": "string", "description": "Civic service type"},
            },
            "required": ["city"],
        }

    def execute(self, city: str, service_type: str = None, **kwargs) -> Dict[str, Any]:
        results = [c for c in SERVICE_CENTERS if c["city"].lower() == city.lower()]
        if service_type:
            results = [c for c in results if service_type.lower() in c["service_type"].lower()]
        return {"success": True, "count": len(results), "service_centers": results}


class BookServiceAppointmentTool(Tool):
    @property
    def name(self) -> str:
        return "book_service_appointment"

    @property
    def description(self) -> str:
        return "Book an appointment at a civic service center."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "center_id": {"type": "string", "description": "Service center ID"},
                "service_type": {"type": "string", "description": "Service type"},
                "date": {"type": "string", "description": "Appointment date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Appointment time (HH:MM)"},
                "applicant_name": {"type": "string", "description": "Applicant name"},
                "phone": {"type": "string", "description": "Applicant phone number"},
            },
            "required": ["center_id", "service_type", "date", "time", "applicant_name", "phone"],
        }

    def execute(self, center_id: str, service_type: str, date: str, time: str, applicant_name: str, phone: str, **kwargs) -> Dict[str, Any]:
        if not _find_center(center_id):
            return {"success": False, "error": f"Service center not found: {center_id}"}
        appointment = {
            "appointment_id": "civappt_" + "".join(random.choices(string.digits, k=6)),
            "center_id": center_id,
            "service_type": service_type,
            "date": date,
            "time": time,
            "applicant_name": applicant_name,
            "phone": phone,
            "status": "Booked",
        }
        return {"success": True, "message": "Service appointment booked", "appointment": appointment}


class CheckCivicApplicationStatusTool(Tool):
    @property
    def name(self) -> str:
        return "check_application_status"

    @property
    def description(self) -> str:
        return "Check civic application status by application ID."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "application_id": {"type": "string", "description": "Application ID"}
            },
            "required": ["application_id"],
        }

    def execute(self, application_id: str, **kwargs) -> Dict[str, Any]:
        application = CIVIC_APPLICATIONS.get(application_id)
        if not application:
            return {"success": False, "error": f"Application not found: {application_id}"}
        return {"success": True, "application": application}


class RequiredDocumentsTool(Tool):
    @property
    def name(self) -> str:
        return "get_required_documents"

    @property
    def description(self) -> str:
        return "Get required documents for a civic service at a service center."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "center_id": {"type": "string", "description": "Service center ID"}
            },
            "required": ["center_id"],
        }

    def execute(self, center_id: str, **kwargs) -> Dict[str, Any]:
        center = _find_center(center_id)
        if not center:
            return {"success": False, "error": f"Service center not found: {center_id}"}
        return {
            "success": True,
            "center_id": center_id,
            "service_type": center["service_type"],
            "required_documents": center["required_documents"],
        }
