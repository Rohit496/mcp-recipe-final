import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Final

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError

mcp = MCPServer("Library Management System", version="1.0.0")

JSON_MIME: Final = "application/json"
FINE_PER_DAY: Final = 0.50

# Mock database - In production, this would be a real database
LIBRARY_DATA: Final[dict[str, list[dict[str, Any]]]] = {
    "books": [
        {
            "id": "B001",
            "title": "Artificial Intelligence: A Modern Approach",
            "authors": ["Stuart Russell", "Peter Norvig"],
            "isbn": "978-0134610993",
            "category": "Computer Science",
            "publisher": "Pearson",
            "publication_year": 2020,
            "copies_total": 5,
            "copies_available": 2,
            "location": "CS-Section-A-Shelf-12",
            "status": "available",
            "last_updated": "2024-01-15T10:30:00Z",
        },
        {
            "id": "B002",
            "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
            "authors": ["Robert C. Martin"],
            "isbn": "978-0132350884",
            "category": "Software Engineering",
            "publisher": "Prentice Hall",
            "publication_year": 2008,
            "copies_total": 3,
            "copies_available": 0,
            "location": "SE-Section-B-Shelf-05",
            "status": "checked_out",
            "last_updated": "2024-01-20T14:15:00Z",
        },
        {
            "id": "B003",
            "title": "The Design of Everyday Things",
            "authors": ["Donald A. Norman"],
            "isbn": "978-0465050659",
            "category": "Design",
            "publisher": "Basic Books",
            "publication_year": 2013,
            "copies_total": 4,
            "copies_available": 4,
            "location": "DESIGN-Section-C-Shelf-03",
            "status": "available",
            "last_updated": "2024-01-18T09:45:00Z",
        },
        {
            "id": "B004",
            "title": "Database System Concepts",
            "authors": ["Abraham Silberschatz", "Henry Korth", "S. Sudarshan"],
            "isbn": "978-0078022159",
            "category": "Database Systems",
            "publisher": "McGraw-Hill",
            "publication_year": 2019,
            "copies_total": 6,
            "copies_available": 1,
            "location": "DB-Section-A-Shelf-18",
            "status": "available",
            "last_updated": "2024-01-22T16:20:00Z",
        },
    ],
    "members": [
        {
            "id": "M001",
            "name": "Alice Johnson",
            "email": "alice.johnson@university.edu",
            "member_type": "faculty",
            "registration_date": "2023-09-01T00:00:00Z",
            "books_checked_out": ["B002"],
            "max_books": 10,
            "status": "active",
        },
        {
            "id": "M002",
            "name": "Bob Smith",
            "email": "bob.smith@university.edu",
            "member_type": "student",
            "registration_date": "2023-09-15T00:00:00Z",
            "books_checked_out": [],
            "max_books": 5,
            "status": "active",
        },
    ],
    "checkouts": [
        {
            "id": "CO001",
            "book_id": "B002",
            "member_id": "M001",
            "checkout_date": "2024-01-20T14:15:00Z",
            "due_date": "2024-02-20T14:15:00Z",
            "return_date": None,
            "status": "active",
            "renewal_count": 0,
        }
    ],
    "reservations": [
        {
            "id": "R001",
            "book_id": "B002",
            "member_id": "M002",
            "reservation_date": "2024-01-21T10:00:00Z",
            "status": "active",
            "priority": 1,
        }
    ],
}


def _now() -> datetime:
    return datetime.now(UTC)


def _to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def _percent(part: int, whole: int) -> str:
    return f"{part / whole * 100:.1f}%" if whole else "0.0%"


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _by_id(collection: str) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in LIBRARY_DATA[collection]}


def _active(collection: str) -> list[dict[str, Any]]:
    return [item for item in LIBRARY_DATA[collection] if item["status"] == "active"]


def _slugify(text: str) -> str:
    return "-".join(text.lower().replace("_", " ").replace("-", " ").split())


@mcp.resource("library://catalog", title="Full Catalog", mime_type=JSON_MIME)
def get_full_catalog() -> str:
    """Complete library catalog with all books and their details."""
    books = LIBRARY_DATA["books"]
    return _to_json(
        {
            "total_books": len(books),
            "generated_at": _now().isoformat(),
            "books": books,
        }
    )


@mcp.resource("library://available", title="Available Books", mime_type=JSON_MIME)
def get_available_books() -> str:
    """Books with at least one copy currently available for checkout."""
    books = LIBRARY_DATA["books"]
    available = [book for book in books if book["copies_available"] > 0]
    return _to_json(
        {
            "available_count": len(available),
            "total_books": len(books),
            "availability_rate": _percent(len(available), len(books)),
            "books": available,
        }
    )


@mcp.resource("library://categories", title="Categories", mime_type=JSON_MIME)
def get_categories() -> str:
    """All book categories with the slug to use in library://category/{category}."""
    counts = Counter(book["category"] for book in LIBRARY_DATA["books"])
    return _to_json(
        {
            "categories": [
                {"name": name, "slug": _slugify(name), "book_count": count}
                for name, count in sorted(counts.items())
            ]
        }
    )


@mcp.resource(
    "library://category/{category}", title="Books by Category", mime_type=JSON_MIME
)
def get_books_by_category(category: str) -> str:
    """Books in one category. Accepts a slug ("computer-science") or name ("Computer Science")."""
    slug = _slugify(category)
    books = [b for b in LIBRARY_DATA["books"] if _slugify(b["category"]) == slug]
    if not books:
        known = sorted({_slugify(b["category"]) for b in LIBRARY_DATA["books"]})
        raise ResourceNotFoundError(
            f"Unknown category {category!r}. Valid categories: {', '.join(known)}"
        )
    return _to_json(
        {
            "category": books[0]["category"],
            "book_count": len(books),
            "books": books,
        }
    )


@mcp.resource("library://members", title="Members", mime_type=JSON_MIME)
def get_member_information() -> str:
    """Library members with their current checkouts and overdue flags."""
    members = LIBRARY_DATA["members"]
    books = _by_id("books")
    now = _now()

    enriched: list[dict[str, Any]] = []
    for member in members:
        current: list[dict[str, Any]] = [
            {
                "book_id": checkout["book_id"],
                "book_title": books[checkout["book_id"]]["title"],
                "checkout_date": checkout["checkout_date"],
                "due_date": checkout["due_date"],
                "is_overdue": _parse_ts(checkout["due_date"]) < now,
            }
            for checkout in _active("checkouts")
            if checkout["member_id"] == member["id"] and checkout["book_id"] in books
        ]
        enriched.append(
            {
                **member,
                "current_checkouts": current,
                "books_checked_out_count": len(current),
            }
        )

    return _to_json(
        {
            "total_members": len(members),
            "active_members": len(_active("members")),
            "members": enriched,
        }
    )


@mcp.resource("library://overdue", title="Overdue Books", mime_type=JSON_MIME)
def get_overdue_books() -> str:
    """Overdue checkouts with member contact details and accrued fines."""
    books = _by_id("books")
    members = _by_id("members")
    now = _now()

    overdue: list[dict[str, Any]] = []
    for checkout in _active("checkouts"):
        due = _parse_ts(checkout["due_date"])
        book = books.get(checkout["book_id"])
        member = members.get(checkout["member_id"])
        if due >= now or book is None or member is None:
            continue
        days_overdue = (now - due).days
        overdue.append(
            {
                "book_id": book["id"],
                "book_title": book["title"],
                "member_name": member["name"],
                "member_email": member["email"],
                "checkout_date": checkout["checkout_date"],
                "due_date": checkout["due_date"],
                "days_overdue": days_overdue,
                "fine_amount": round(days_overdue * FINE_PER_DAY, 2),
            }
        )

    return _to_json(
        {
            "overdue_count": len(overdue),
            "fine_per_day": FINE_PER_DAY,
            "total_fine_amount": round(sum(i["fine_amount"] for i in overdue), 2),
            "overdue_items": overdue,
        }
    )


@mcp.resource("library://stats", title="Library Statistics", mime_type=JSON_MIME)
def get_library_statistics() -> str:
    """Collection, membership, circulation and per-category statistics."""
    books = LIBRARY_DATA["books"]
    members = LIBRARY_DATA["members"]

    total_copies = sum(book["copies_total"] for book in books)
    available_copies = sum(book["copies_available"] for book in books)
    checked_out_copies = total_copies - available_copies

    categories: dict[str, dict[str, int]] = {}
    for book in books:
        entry = categories.setdefault(book["category"], {"count": 0, "available": 0})
        entry["count"] += 1
        entry["available"] += book["copies_available"] > 0

    return _to_json(
        {
            "collection_stats": {
                "total_titles": len(books),
                "total_copies": total_copies,
                "available_copies": available_copies,
                "checked_out_copies": checked_out_copies,
                "utilization_rate": _percent(checked_out_copies, total_copies),
            },
            "member_stats": {
                "total_members": len(members),
                "active_members": len(_active("members")),
                "member_types": dict(Counter(m["member_type"] for m in members)),
            },
            "circulation_stats": {
                "active_checkouts": len(_active("checkouts")),
                "active_reservations": len(_active("reservations")),
            },
            "category_breakdown": categories,
            "generated_at": _now().isoformat(),
        }
    )


if __name__ == "__main__":
    mcp.run()
