import sqlite3
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("SQLite Server")

DB_PATH = Path(__file__).parent / "db"


def dict_from_row(row: sqlite3.Row | None) -> dict[str, Any]:
    """Convert sqlite3.Row to dictionary."""
    return dict(row) if row else {}


def dicts_from_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert list of sqlite3.Row to list of dictionaries."""
    return [dict(row) for row in rows]


def get_db_connection(db_name: str) -> sqlite3.Connection:
    """Create and return a database connection."""
    conn = sqlite3.connect(DB_PATH / db_name)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


@mcp.tool()
def search_countries(name: str = "") -> list[dict[str, Any]]:
    """
    Search for countries by name.

    Args:
        name: Country name to search for (partial matches allowed)

    Returns:
        List of countries matching the search
    """
    conn = get_db_connection(db_name="world.db")

    if name:
        query = "SELECT * FROM countries WHERE name LIKE ? ORDER BY name LIMIT 20"
        params = [f"%{name}%"]
    else:
        query = "SELECT * FROM countries ORDER BY name LIMIT 20"
        params = []

    cursor = conn.execute(query, params)
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


@mcp.tool()
def get_countries(name: str = "") -> list[dict[str, Any]]:
    """
    Simple country search by name.

    Args:
        name: Country name to search for. This is optional. Default, return all countries from the database.

    Returns:
        List of matching countries
    """
    conn = get_db_connection(db_name="world.db")

    if name:
        print(f"Searching for countries with name: '{name}'", file=sys.stderr)
        query = "SELECT * FROM countries WHERE name LIKE ? ORDER BY name LIMIT 10"
        params = [f"%{name}%"]
    else:
        print("No name provided, returning first 10 countries", file=sys.stderr)
        query = "SELECT * FROM countries ORDER BY name LIMIT 197"
        params = []

    print(f"Query: {query}", file=sys.stderr)
    print(f"Params: {params}", file=sys.stderr)

    cursor = conn.execute(query, params)
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    print(f"Found {len(results)} results", file=sys.stderr)
    return results


@mcp.tool()
def get_country(country_code: str) -> dict[str, Any]:
    """
    Get detailed information about a specific country.

    Args:
        country_code: Two-letter ISO country code (e.g., "US", "GB", "FR")

    Returns:
        Complete country information
    """
    conn = get_db_connection(db_name="world.db")

    cursor = conn.execute(
        "SELECT * FROM countries WHERE iso2 = ?", [country_code.upper()]
    )
    result = cursor.fetchone()
    conn.close()

    return dict_from_row(result)


@mcp.tool()
def get_countries_by_region(region: str) -> list[dict[str, Any]]:
    """
    Get all countries in a specific region.

    Args:
        region: Region name (e.g., "Europe", "Asia", "Africa")

    Returns:
        List of countries in the region
    """
    conn = get_db_connection(db_name="world.db")

    cursor = conn.execute(
        "SELECT * FROM countries WHERE region LIKE ? ORDER BY name", [f"%{region}%"]
    )
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


@mcp.tool()
def get_countries_by_currency(currency: str) -> list[dict[str, Any]]:
    """
    Find all countries that use a specific currency.

    Args:
        currency: Currency code (e.g., "USD", "EUR", "GBP")

    Returns:
        List of countries using the currency
    """
    conn = get_db_connection(db_name="world.db")

    cursor = conn.execute(
        "SELECT * FROM countries WHERE currency = ? ORDER BY name", [currency.upper()]
    )
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


# =============================================================================
# CITY TOOLS
# =============================================================================


@mcp.tool()
def search_cities(name: str = "", country_code: str = "") -> list[dict[str, Any]]:
    """
    Search for cities by name and optionally filter by country.

    Args:
        name: City name to search for (partial matches allowed)
        country_code: Two-letter country code to filter by (optional)

    Returns:
        List of cities matching the search criteria
    """
    conn = get_db_connection(db_name="world.db")

    query = "SELECT * FROM cities WHERE 1=1"
    params: list[str] = []

    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")

    if country_code:
        query += " AND country_code = ?"
        params.append(country_code.upper())

    query += " ORDER BY name LIMIT 30"

    cursor = conn.execute(query, params)
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


@mcp.tool()
def get_cities_in_country(country_code: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    Get cities in a specific country.

    Args:
        country_code: Two-letter country code (e.g., "US", "GB", "FR")
        limit: Maximum number of cities to return (default 50)

    Returns:
        List of cities in the country
    """
    conn = get_db_connection(db_name="world.db")

    cursor = conn.execute(
        "SELECT * FROM cities WHERE country_code = ? ORDER BY name LIMIT ?",
        [country_code.upper(), limit],
    )
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


# =============================================================================
# STATE/PROVINCE TOOLS
# =============================================================================


@mcp.tool()
def search_states(name: str = "", country_code: str = "") -> list[dict[str, Any]]:
    """
    Search for states/provinces by name and optionally filter by country.

    Args:
        name: State/province name to search for (partial matches allowed)
        country_code: Two-letter country code to filter by (optional)

    Returns:
        List of states/provinces matching the search criteria
    """
    conn = get_db_connection(db_name="world.db")

    query = "SELECT * FROM states WHERE 1=1"
    params: list[str] = []

    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")

    if country_code:
        query += " AND country_code = ?"
        params.append(country_code.upper())

    query += " ORDER BY name LIMIT 30"

    cursor = conn.execute(query, params)
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


@mcp.tool()
def get_states_in_country(country_code: str) -> list[dict[str, Any]]:
    """
    Get all states/provinces in a specific country.

    Args:
        country_code: Two-letter country code (e.g., "US", "CA", "AU")

    Returns:
        List of states/provinces in the country
    """
    conn = get_db_connection(db_name="world.db")

    cursor = conn.execute(
        "SELECT * FROM states WHERE country_code = ? ORDER BY name",
        [country_code.upper()],
    )
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


# =============================================================================
# REGION TOOLS
# =============================================================================


@mcp.tool()
def get_all_regions() -> list[dict[str, Any]]:
    """
    Get all world regions.

    Returns:
        List of all regions
    """
    conn = get_db_connection(db_name="world.db")

    cursor = conn.execute("SELECT * FROM regions ORDER BY name")
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


@mcp.tool()
def get_subregions_in_region(region_id: int) -> list[dict[str, Any]]:
    """
    Get all subregions within a specific region.

    Args:
        region_id: The ID of the parent region

    Returns:
        List of subregions in the region
    """
    conn = get_db_connection(db_name="world.db")

    cursor = conn.execute(
        "SELECT * FROM subregions WHERE region_id = ? ORDER BY name", [region_id]
    )
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


# =============================================================================
# STATISTICS AND SUMMARY TOOLS
# =============================================================================


@mcp.tool()
def get_database_stats() -> dict[str, int]:
    """
    Get statistics about the database contents.

    Returns:
        Dictionary with counts of countries, cities, states, regions, and subregions
    """
    conn = get_db_connection(db_name="world.db")

    stats: dict[str, int] = {}

    # Count each table
    tables = ["countries", "cities", "states", "regions", "subregions"]
    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
        stats[f"total_{table}"] = cursor.fetchone()["count"]

    conn.close()

    return stats


@mcp.tool()
def get_countries_summary() -> list[dict[str, Any]]:
    """
    Get a summary of all countries with basic information.

    Returns:
        List of countries with just name, code, capital, and region
    """
    conn = get_db_connection(db_name="world.db")

    cursor = conn.execute(
        "SELECT name, iso2, capital, region FROM countries ORDER BY name"
    )
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


@mcp.tool()
def get_popular_currencies() -> list[dict[str, Any]]:
    """
    Get the most commonly used currencies and how many countries use them.

    Returns:
        List of currencies with usage counts, ordered by popularity
    """
    conn = get_db_connection(db_name="world.db")

    cursor = conn.execute("""SELECT currency, currency_name, COUNT(*) as country_count
           FROM countries 
           WHERE currency IS NOT NULL
           GROUP BY currency, currency_name
           ORDER BY country_count DESC
           LIMIT 20""")
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


@mcp.tool()
def get_top_chatters() -> list[dict[str, Any]]:
    """Retrieve the top chatters sorted by number of messages."""
    conn = get_db_connection(db_name="community.db")

    cursor = conn.execute("SELECT name, messages FROM chatters ORDER BY messages DESC")
    results = dicts_from_rows(cursor.fetchall())
    conn.close()

    return results


if __name__ == "__main__":
    mcp.run()
