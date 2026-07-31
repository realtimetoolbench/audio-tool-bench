"""
Library tools (book search, reservation, renewal)
"""
from typing import Dict, Any
import random
import string
from datetime import datetime, timedelta

from .base import Tool
from .mock_data import BOOKS


class BookSearchTool(Tool):
    """Book search tool"""

    def __init__(self):
        self.books = BOOKS

    @property
    def name(self) -> str:
        return "search_books"

    @property
    def description(self) -> str:
        return "Search for books by title, author, and category."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                # TODO: optional 参数暂时禁用
                # "keyword": {"type": "string", "description": "Search keyword (title or author)"},
                # "category": {"type": "string", "description": "Category (Computer Science, Literature, Science Fiction, History)"},
                # "author": {"type": "string", "description": "Author name"},
                # "only_available": {"type": "boolean", "description": "Only show available books"}
            },
            "required": []
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        keyword = kwargs.get("keyword", "").lower()
        category = kwargs.get("category")
        author = kwargs.get("author")
        only_available = kwargs.get("only_available", False)

        results = self.books.copy()

        if keyword:
            results = [b for b in results if keyword in b["title"].lower() or keyword in b["author"].lower()]
        if category:
            results = [b for b in results if category.lower() in b["category"].lower()]
        if author:
            results = [b for b in results if author.lower() in b["author"].lower()]
        if only_available:
            results = [b for b in results if b["available_copies"] > 0]

        return {
            "success": True,
            "count": len(results),
            "books": results
        }


class ReserveBookTool(Tool):
    """Book reservation tool"""

    def __init__(self):
        self.reservations = []

    @property
    def name(self) -> str:
        return "reserve_book"

    @property
    def description(self) -> str:
        return "Reserve a book with book ID and reader info."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "book_id": {"type": "string", "description": "Book ID (ISBN)"},
                # TODO: optional 参数暂时禁用
                # "reader_id": {"type": "string", "description": "Reader card number"},
                "reader_name": {"type": "string", "description": "Reader name"}
                # "pickup_date": {"type": "string", "description": "Expected pickup date (YYYY-MM-DD, default: 3 days later)"}
            },
            "required": ["book_id", "reader_name"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        book_id = kwargs.get("book_id")
        reader_id = kwargs.get("reader_id")
        reader_name = kwargs.get("reader_name")
        pickup_date = kwargs.get("pickup_date")

        if not pickup_date:
            pickup_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

        reservation_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        reservation = {
            "reservation_id": reservation_id,
            "book_id": book_id,
            "reader_id": reader_id,
            "reader_name": reader_name,
            "pickup_date": pickup_date,
            "reservation_date": timestamp,
            "status": "Reserved",
            "valid_until": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        }

        self.reservations.append(reservation)

        return {
            "success": True,
            "message": "Reservation successful, please pick up within the valid period",
            "reservation": reservation
        }


class RenewBookTool(Tool):
    """Book renewal tool"""

    def __init__(self):
        self.loans = {
            "L20260201001": {
                "loan_id": "L20260201001",
                "book_id": "ISBN9787115583949",
                "book_title": "Python Crash Course",
                "reader_id": "R123456",
                "reader_name": "John Smith",
                "borrow_date": "2026-02-01",
                "due_date": "2026-03-11",
                "renew_count": 0,
                "max_renew": 2
            },
            "L20260205001": {
                "loan_id": "L20260205001",
                "book_id": "ISBN9787020008735",
                "book_title": "To Live",
                "reader_id": "R123456",
                "reader_name": "John Smith",
                "borrow_date": "2026-02-05",
                "due_date": "2026-03-15",
                "renew_count": 1,
                "max_renew": 2
            }
        }

    @property
    def name(self) -> str:
        return "renew_book"

    @property
    def description(self) -> str:
        return "Renew a borrowed book with loan ID."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "loan_id": {"type": "string", "description": "Loan ID"}
            },
            "required": ["loan_id"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        loan_id = kwargs.get("loan_id")

        if loan_id not in self.loans:
            return {
                "success": False,
                "error": "Loan record not found"
            }

        loan = self.loans[loan_id]

        if loan["renew_count"] >= loan["max_renew"]:
            return {
                "success": False,
                "error": f"Maximum renewal limit reached ({loan['max_renew']} times)"
            }

        old_due_date = loan["due_date"]
        new_due_date = (datetime.strptime(old_due_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")

        loan["due_date"] = new_due_date
        loan["renew_count"] += 1

        return {
            "success": True,
            "message": "Renewal successful",
            "loan": loan,
            "old_due_date": old_due_date,
            "new_due_date": new_due_date,
            "remaining_renews": loan["max_renew"] - loan["renew_count"]
        }
