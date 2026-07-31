"""
Course enrollment tools
"""
from typing import Dict, Any
import random
import string
from datetime import datetime

from .base import Tool
from .mock_data import COURSES


class CourseSearchTool(Tool):
    """Course search tool"""

    def __init__(self):
        self.courses = COURSES

    @property
    def name(self) -> str:
        return "search_courses"

    @property
    def description(self) -> str:
        return "Search for courses by category, instructor, price, and level."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                # TODO: optional 参数暂时禁用
                # "keyword": {"type": "string", "description": "Course keyword (supports fuzzy search)"},
                # "category": {"type": "string", "description": "Category (Programming, Language, Art, Music)", "enum": ["Programming", "Language", "Art", "Music"]},
                # "instructor": {"type": "string", "description": "Instructor name"},
                # "max_price": {"type": "number", "description": "Maximum price"},
                # "level": {"type": "string", "description": "Level (Beginner, Intermediate, Advanced)", "enum": ["Beginner", "Intermediate", "Advanced"]},
                # "has_vacancy": {"type": "boolean", "description": "Only show courses with available spots"}
            },
            "required": []
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        keyword = kwargs.get("keyword", "").lower()
        category = kwargs.get("category")
        instructor = kwargs.get("instructor")
        max_price = kwargs.get("max_price")
        level = kwargs.get("level")
        has_vacancy = kwargs.get("has_vacancy", False)

        results = self.courses.copy()

        if keyword:
            results = [c for c in results if keyword in c["name"].lower()]
        if category:
            results = [c for c in results if c["category"] == category]
        if instructor:
            results = [c for c in results if instructor.lower() in c["instructor"].lower()]
        if max_price is not None:
            results = [c for c in results if c["price"] <= max_price]
        if level:
            results = [c for c in results if c["level"] == level]
        if has_vacancy:
            results = [c for c in results if c["enrolled"] < c["capacity"]]

        return {
            "success": True,
            "count": len(results),
            "courses": results
        }


class EnrollCourseTool(Tool):
    """Course enrollment tool"""

    def __init__(self):
        self.enrollments = []

    @property
    def name(self) -> str:
        return "enroll_course"

    @property
    def description(self) -> str:
        return "Enroll in a course with course ID and student info."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "course_id": {"type": "string", "description": "Course ID"},
                "student_name": {"type": "string", "description": "Student name"}
                # TODO: optional 参数暂时禁用
                # "student_phone": {"type": "string", "description": "Student phone number"},
                # "student_email": {"type": "string", "description": "Student email (optional)"},
                # "payment_method": {"type": "string", "description": "Payment method (full, installment)", "enum": ["full", "installment"], "default": "full"}
            },
            "required": ["course_id", "student_name"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        course_id = kwargs.get("course_id")
        student_name = kwargs.get("student_name")
        student_phone = kwargs.get("student_phone")
        student_email = kwargs.get("student_email", "")
        payment_method = kwargs.get("payment_method", "full")

        enrollment_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        enrollment = {
            "enrollment_id": enrollment_id,
            "course_id": course_id,
            "student_name": student_name,
            "student_phone": student_phone,
            "student_email": student_email,
            "payment_method": payment_method,
            "status": "Enrolled",
            "enrollment_date": timestamp
        }

        self.enrollments.append(enrollment)

        return {
            "success": True,
            "message": "Enrollment successful",
            "enrollment": enrollment
        }
