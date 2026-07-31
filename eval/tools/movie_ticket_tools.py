"""
Movie ticket booking tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import MOVIES


def _find_movie_by_id(movie_id: str):
    """Find movie by movie_id across all cities"""
    for city_movies in MOVIES.values():
        for movie in city_movies:
            if movie.get("movie_id") == movie_id:
                return movie
    return None


class MovieSearchTool(Tool):
    """Movie search tool"""

    def __init__(self):
        self.movies = MOVIES

    @property
    def name(self) -> str:
        return "search_movies"

    @property
    def description(self) -> str:
        return "Search for movies and showtimes in cinemas."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "genre": {"type": "string", "description": "Movie genre (Sci-Fi, Drama, Animation, Comedy, etc.)"}
            },
            "required": ["city"]
        }

    def execute(self, city: str, movie_name: str = None, cinema: str = None, genre: str = None, date: str = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            results = self.movies.get(city, []).copy()

            if not results:
                output = f"No movies found in {city}."
                return {"success": True, "output": output, "raw_output": [], "error": None,
                        "latency_ms": (time.time() - start_time) * 1000}

            if movie_name:
                results = [m for m in results if movie_name.lower() in m["name"].lower()]
            if genre:
                results = [m for m in results if genre.lower() in m["genre"].lower()]
            if cinema:
                results = [m for m in results if any(cinema.lower() in c.lower() for c in m["cinemas"])]

            if not results:
                output = f"No movies found in {city} matching criteria."
            else:
                output = f"Found {len(results)} movies in {city}:\n\n"
                for i, m in enumerate(results, 1):
                    output += f"{i}. {m['name']} (ID: {m['movie_id']})\n"
                    output += f"   Genre: {m['genre']} | Duration: {m['duration']} min\n"
                    output += f"   Rating: {m['rating']}/10.0\n"
                    output += f"   Price: ¥{m['price']}\n"
                    output += f"   Cinemas: {', '.join(m['cinemas'])}\n"
                    output += f"   Showtimes: {', '.join(m['showtimes'])}\n\n"

            return {"success": True, "output": output, "raw_output": results, "error": None,
                    "latency_ms": (time.time() - start_time) * 1000}

        except Exception as e:
            return {"success": False, "output": f"Search failed: {str(e)}", "raw_output": None,
                    "error": str(e), "latency_ms": (time.time() - start_time) * 1000}


class BookMovieTicketTool(Tool):
    """Movie ticket booking tool"""

    def __init__(self):
        self.bookings = []
        self.booking_counter = 60001

    @property
    def name(self) -> str:
        return "book_movie_ticket"

    @property
    def description(self) -> str:
        return "Book movie tickets with seat selection."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "movie_id": {"type": "string", "description": "Movie ID from search results (e.g., 'mov_bj_001')"},
                "cinema": {"type": "string", "description": "Cinema name"},
                "showtime": {"type": "string", "description": "Showtime (e.g., '19:00')"},
                "seat_count": {"type": "integer", "description": "Number of tickets"},
                "buyer_name": {"type": "string", "description": "Buyer name"}
                # TODO: optional 参数暂时禁用
                # "seat_preference": {"type": "string", "description": "Seat preference (front, middle, back)", "default": "middle"},
                # "ticket_type": {"type": "string", "description": "Ticket type (adult, student, child)", "default": "adult"}
            },
            "required": ["movie_id", "cinema", "showtime", "seat_count", "buyer_name"]
        }

    def execute(self, movie_id: str, cinema: str, showtime: str, seat_count: int, buyer_name: str, seat_preference: str = "middle", ticket_type: str = "adult", **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            # Look up movie by ID
            movie = _find_movie_by_id(movie_id)
            if not movie:
                return {
                    "success": False,
                    "output": f"Movie not found: {movie_id}. Please search for movies first.",
                    "raw_output": None,
                    "error": f"Invalid movie_id: {movie_id}",
                    "latency_ms": (time.time() - start_time) * 1000
                }

            movie_name = movie["name"]
            # Use date from showtime context or default to first available
            date = kwargs.get("date", "2026-03-01")

            booking_id = f"MV{self.booking_counter}"
            self.booking_counter += 1

            seat_rows = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
            if seat_preference == "front":
                base_row = seat_rows[1]
            elif seat_preference == "back":
                base_row = seat_rows[7]
            else:
                base_row = seat_rows[4]

            seats = [f"{base_row}{i+5}" for i in range(seat_count)]

            base_price = 45
            if ticket_type == "student":
                base_price = int(base_price * 0.8)
            elif ticket_type == "child":
                base_price = int(base_price * 0.7)

            total_price = base_price * seat_count

            booking = {
                "booking_id": booking_id,
                "movie_id": movie_id,
                "movie_name": movie_name,
                "cinema": cinema,
                "date": date,
                "showtime": showtime,
                "seat_count": seat_count,
                "seats": seats,
                "buyer_name": buyer_name,
                "ticket_type": ticket_type,
                "total_price": total_price,
                "status": "confirmed"
            }
            self.bookings.append(booking)

            output = f"Movie ticket booking successful!\n\n"
            output += f"Booking ID: {booking_id}\n"
            output += f"Movie ID: {movie_id}\n"
            output += f"Movie: {movie_name}\n"
            output += f"Cinema: {cinema}\n"
            output += f"Date: {date}\n"
            output += f"Showtime: {showtime}\n"
            output += f"Seats: {', '.join(seats)}\n"
            output += f"Ticket type: {ticket_type}\n"
            output += f"Quantity: {seat_count}\n"
            output += f"Total: ¥{total_price}\n"
            output += f"Status: Confirmed\n"

            return {"success": True, "output": output, "raw_output": booking, "error": None,
                    "latency_ms": (time.time() - start_time) * 1000}

        except Exception as e:
            return {"success": False, "output": f"Booking failed: {str(e)}", "raw_output": None,
                    "error": str(e), "latency_ms": (time.time() - start_time) * 1000}
