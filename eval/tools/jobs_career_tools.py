"""
Jobs and career tools
"""
from typing import Dict, Any
import random
import string

from .base import Tool
from .mock_data import JOBS, JOB_APPLICATIONS


def _find_job(job_id: str):
    for job in JOBS:
        if job["job_id"] == job_id:
            return job
    return None


class JobSearchTool(Tool):
    @property
    def name(self) -> str:
        return "search_jobs"

    @property
    def description(self) -> str:
        return "Search jobs by keyword, city, and job type."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Job keyword"},
                "city": {"type": "string", "description": "City name"},
                "job_type": {"type": "string", "description": "Job type"},
            },
            "required": [],
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        keyword = (kwargs.get("keyword") or "").lower()
        city = kwargs.get("city")
        job_type = kwargs.get("job_type")
        results = JOBS.copy()
        if keyword:
            results = [j for j in results if keyword in j["title"].lower() or keyword in j["company"].lower()]
        if city:
            results = [j for j in results if j["city"].lower() == city.lower()]
        if job_type:
            results = [j for j in results if j["job_type"].lower() == job_type.lower()]
        return {"success": True, "count": len(results), "jobs": results}


class JobDetailsTool(Tool):
    @property
    def name(self) -> str:
        return "get_job_details"

    @property
    def description(self) -> str:
        return "Get job details by job ID."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID from search_jobs"}
            },
            "required": ["job_id"],
        }

    def execute(self, job_id: str, **kwargs) -> Dict[str, Any]:
        job = _find_job(job_id)
        if not job:
            return {"success": False, "error": f"Job not found: {job_id}"}
        return {"success": True, "job": job}


class SaveJobTool(Tool):
    @property
    def name(self) -> str:
        return "save_job"

    @property
    def description(self) -> str:
        return "Save a job for later review."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID"},
                "candidate_name": {"type": "string", "description": "Candidate name"},
            },
            "required": ["job_id", "candidate_name"],
        }

    def execute(self, job_id: str, candidate_name: str, **kwargs) -> Dict[str, Any]:
        if not _find_job(job_id):
            return {"success": False, "error": f"Job not found: {job_id}"}
        saved = {
            "saved_id": "saved_" + "".join(random.choices(string.digits, k=6)),
            "job_id": job_id,
            "candidate_name": candidate_name,
            "status": "Saved",
        }
        return {"success": True, "message": "Job saved", "saved_job": saved}


class DraftApplicationTool(Tool):
    @property
    def name(self) -> str:
        return "draft_application"

    @property
    def description(self) -> str:
        return "Draft a job application for a job."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID"},
                "candidate_name": {"type": "string", "description": "Candidate name"},
                "cover_letter": {"type": "string", "description": "Cover letter text"},
            },
            "required": ["job_id", "candidate_name", "cover_letter"],
        }

    def execute(self, job_id: str, candidate_name: str, cover_letter: str, **kwargs) -> Dict[str, Any]:
        if not _find_job(job_id):
            return {"success": False, "error": f"Job not found: {job_id}"}
        draft = {
            "draft_id": "appdraft_" + "".join(random.choices(string.digits, k=6)),
            "job_id": job_id,
            "candidate_name": candidate_name,
            "cover_letter": cover_letter,
            "status": "Drafted",
        }
        return {"success": True, "message": "Application drafted", "draft": draft}


class TrackApplicationStatusTool(Tool):
    @property
    def name(self) -> str:
        return "track_application_status"

    @property
    def description(self) -> str:
        return "Track job application status by application ID."

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
        application = JOB_APPLICATIONS.get(application_id)
        if not application:
            return {"success": False, "error": f"Application not found: {application_id}"}
        return {"success": True, "application": application}
