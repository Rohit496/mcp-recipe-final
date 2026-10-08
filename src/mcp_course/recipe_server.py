import json
import logging
import os
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from mcp.server.mcpserver import MCPServer

type JSONDict = dict[str, Any]

logger = logging.getLogger(__name__)

# Use pathlib for cross-platform compatibility
SCRIPT_DIR = Path(__file__).parent.resolve()
RECIPES_DIR = SCRIPT_DIR / "recipes"

MEALDB_BASE_URL = "https://www.themealdb.com/api/json/v1/1"
INVALID_FILENAME_CHARS = '<>:"/\\|?*'
NON_COLLECTION_DIRS = {"meal_plans", "by_letter"}

# Errors from local file I/O (OSError) and malformed JSON/API data
DATA_ERRORS = (OSError, ValueError, KeyError, TypeError)


# ==================== MCP SERVER SETUP ====================
port = int(os.environ.get("PORT", "8000"))

# Initialize MCP server (mcp 2.x: host/port are passed to run(), not the constructor)
mcp = MCPServer("recipe_research")


def _init_recipes_dir() -> None:
    """Create the recipes directory and confirm it is writable."""
    try:
        RECIPES_DIR.mkdir(mode=0o755, exist_ok=True)
        logger.info("Recipes directory ready: %s", RECIPES_DIR)

        # Test write permissions
        test_file = RECIPES_DIR / ".write_test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        logger.info("Write permissions confirmed for: %s", RECIPES_DIR)
    except OSError:
        logger.warning("Recipes directory %s is not usable", RECIPES_DIR, exc_info=True)


_init_recipes_dir()


# ==================== HELPERS ====================


def _sanitize_name(name: str, fallback: str) -> str:
    """Turn arbitrary text into a filename that is valid on Windows, macOS and Linux."""
    safe = name.lower()
    for char in INVALID_FILENAME_CHARS:
        safe = safe.replace(char, "_")
    safe = safe.replace(" ", "_")

    # Remove leading/trailing dots or spaces (Windows compatibility) and cap length
    safe = safe.strip(". ")[:200]

    # Ensure it's not empty or just underscores
    if not safe.replace("_", "").strip():
        return fallback
    return safe


def _fetch_meals(endpoint: str) -> list[JSONDict]:
    """Call a TheMealDB endpoint and return its `meals` list (empty if none)."""
    response = requests.get(f"{MEALDB_BASE_URL}/{endpoint}", timeout=10)
    response.raise_for_status()
    meals: list[JSONDict] | None = response.json().get("meals")
    return meals or []


def _parse_meal(meal: JSONDict) -> JSONDict:
    """Convert a raw TheMealDB meal into our recipe format."""
    # TheMealDB has up to 20 ingredients as strIngredient1..20 / strMeasure1..20
    ingredients: list[dict[str, str]] = []
    for i in range(1, 21):
        ingredient: str | None = meal.get(f"strIngredient{i}")
        measure: str | None = meal.get(f"strMeasure{i}")
        if ingredient and ingredient.strip():
            ingredients.append(
                {
                    "ingredient": ingredient.strip(),
                    "measure": measure.strip() if measure else "",
                }
            )

    tags: str | None = meal.get("strTags")
    return {
        "name": meal.get("strMeal", "Unknown"),
        "cuisine": meal.get("strArea", "Unknown"),
        "category": meal.get("strCategory", "Unknown"),
        "instructions": meal.get("strInstructions", "No instructions available"),
        "image_url": meal.get("strMealThumb", ""),
        "youtube_url": meal.get("strYoutube", ""),
        "source_url": meal.get("strSource", ""),
        "ingredients": ingredients,
        "tags": tags.split(",") if tags else [],
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _collection_dirs() -> list[Path]:
    """Dish/cuisine folders that contain a saved recipes_info.json."""
    if not RECIPES_DIR.exists():
        return []
    return [
        d
        for d in RECIPES_DIR.iterdir()
        if d.is_dir()
        and d.name not in NON_COLLECTION_DIRS
        and (d / "recipes_info.json").exists()
    ]


# ==================== TOOLS ====================


@mcp.tool()
def search_recipes(dish_name: str, max_results: int = 5) -> list[str]:
    """
    Search for recipes by dish name. Extract ONLY the dish/food name from the user's query.

    Examples:
    - User says "Search for Arrabiata recipes" -> dish_name should be "Arrabiata"
    - User says "Find me some pasta recipes" -> dish_name should be "pasta"
    - User says "I want chicken curry recipes" -> dish_name should be "chicken curry"
    - User says "Show me pizza recipes with 5 results" -> dish_name should be "pizza"

    Args:
        dish_name: ONLY the dish/food name (e.g., "Arrabiata", "pasta", "chicken", "pizza", "curry")
        max_results: Number of results to return (extract from user query if specified, default: 5)

    Returns:
        List of recipe IDs found in the search
    """
    try:
        meals = _fetch_meals(f"search.php?s={dish_name}")[:max_results]
    except requests.RequestException as e:
        return [f"Error fetching recipes: {e}"]
    except ValueError as e:
        return [f"Error in search_recipes: {e}"]

    if not meals:
        return [f"No recipes found for dish: {dish_name}"]

    dish_path = RECIPES_DIR / _sanitize_name(dish_name, "unknown_dish")
    try:
        dish_path.mkdir(mode=0o755, exist_ok=True)
    except OSError as e:
        return [f"Cannot create dish directory {dish_path}: {e}"]

    file_path = dish_path / "recipes_info.json"

    # Try to load existing recipes info
    recipes_info: dict[str, JSONDict] = {}
    if file_path.exists():
        try:
            recipes_info = _load_json(file_path)
        except DATA_ERRORS as e:
            logger.warning("Could not load existing file %s: %s", file_path, e)

    recipe_ids: list[str] = []
    try:
        for meal in meals:
            recipe_id: str = meal["idMeal"]
            recipe_ids.append(recipe_id)
            recipes_info[recipe_id] = _parse_meal(meal)
    except DATA_ERRORS as e:
        return [f"Error in search_recipes: {e}"]

    # Save updated recipes_info; return recipe IDs even if save fails
    try:
        _save_json(file_path, recipes_info)
        logger.info("Results saved to: %s", file_path)
    except OSError as e:
        logger.warning("Could not save to file %s: %s", file_path, e)
    return recipe_ids


@mcp.tool()
def get_recipe_details(recipe_id: str) -> str:
    """
    Get detailed information about a specific recipe using its ID.

    Examples:
    - User says "Get details for recipe 52771" -> recipe_id should be "52771"
    - User says "Show me information about recipe ID 52772" -> recipe_id should be "52772"
    - User says "Tell me about recipe 52773" -> recipe_id should be "52773"

    Args:
        recipe_id: ONLY the numeric recipe ID (extract the ID number from user's request)

    Returns:
        JSON string with detailed recipe information if found, error message if not found
    """
    if not RECIPES_DIR.exists():
        return f"Recipes directory {RECIPES_DIR} does not exist."

    try:
        for collection_dir in _collection_dirs():
            file_path = collection_dir / "recipes_info.json"
            try:
                recipes_info: dict[str, JSONDict] = _load_json(file_path)
            except DATA_ERRORS as e:
                logger.warning("Error reading %s: %s", file_path, e)
                continue
            if recipe_id in recipes_info:
                return json.dumps(recipes_info[recipe_id], indent=2)
    except OSError as e:
        return f"Error in get_recipe_details: {e}"

    return f"No saved information found for recipe {recipe_id}."


@mcp.tool()
def create_meal_plan(recipe_ids: list[str], plan_name: str = "My Meal Plan") -> str:
    """
    Create a meal plan from selected recipe IDs. Extract recipe IDs and plan name from user query.

    Examples:
    - User says "Create meal plan with recipes 52771,52772,52773 called 'Italian Week'"
      -> recipe_ids should be ["52771", "52772", "52773"], plan_name should be "Italian Week"
    - User says "Make a meal plan named 'Dinner Ideas' using recipes 52774 and 52775"
      -> recipe_ids should be ["52774", "52775"], plan_name should be "Dinner Ideas"

    Args:
        recipe_ids: List of recipe ID numbers as strings (extract all IDs from user request)
        plan_name: Name for the meal plan (extract name from user request, default: "My Meal Plan")

    Returns:
        Success message with meal plan details or error message
    """
    # Collect recipe details for the meal plan
    meal_plan_recipes: list[dict[str, str]] = []
    for recipe_id in recipe_ids:
        recipe_details = get_recipe_details(recipe_id)
        if recipe_details.startswith(
            ("No saved information", "Error", "Recipes directory")
        ):
            continue
        recipe_data: JSONDict = json.loads(recipe_details)
        meal_plan_recipes.append(
            {
                "id": recipe_id,
                "name": recipe_data.get("name", "Unknown Recipe"),
                "cuisine": recipe_data.get("cuisine", "Unknown"),
                "category": recipe_data.get("category", "Unknown"),
            }
        )

    meal_plan: JSONDict = {
        "plan_name": plan_name,
        "created_date": datetime.now(UTC).isoformat(),
        "total_recipes": len(meal_plan_recipes),
        "recipes": meal_plan_recipes,
    }

    try:
        meal_plans_dir = RECIPES_DIR / "meal_plans"
        meal_plans_dir.mkdir(mode=0o755, exist_ok=True)
        plan_file = meal_plans_dir / f"{_sanitize_name(plan_name, 'meal_plan')}.json"
        _save_json(plan_file, meal_plan)
    except OSError as e:
        return f"Error creating meal plan: {e}"

    return f"Meal plan '{plan_name}' created successfully with {len(meal_plan_recipes)} recipes. Saved to: {plan_file}"


@mcp.tool()
def search_by_first_letter(letter: str, max_results: int = 5) -> list[str]:
    """
    Search for recipes that start with a specific letter. Extract ONLY the single letter from user query.

    Examples:
    - User says "Show me recipes starting with A" -> letter should be "A"
    - User says "Find dishes that begin with the letter B" -> letter should be "B"
    - User says "Get recipes starting with letter C" -> letter should be "C"

    Args:
        letter: ONLY a single letter A-Z (extract the letter from user's request)
        max_results: Number of results to return (default: 5)

    Returns:
        List of recipe IDs found in the search
    """
    if len(letter) != 1 or not letter.isalpha():
        return ["Please provide a single letter (a-z)"]

    try:
        meals = _fetch_meals(f"search.php?f={letter.lower()}")[:max_results]
        if not meals:
            return [f"No recipes found starting with letter: {letter}"]

        recipe_ids: list[str] = [meal["idMeal"] for meal in meals]

        # Save a simple summary file to the letters directory
        letters_dir = RECIPES_DIR / "by_letter"
        letters_dir.mkdir(mode=0o755, exist_ok=True)
        summary: JSONDict = {
            "letter": letter.upper(),
            "found_recipes": len(recipe_ids),
            "recipe_ids": recipe_ids,
            "recipe_names": [meal["strMeal"] for meal in meals],
        }
        _save_json(letters_dir / f"letter_{letter.lower()}_search.json", summary)
    except requests.RequestException as e:
        return [f"Error searching by letter: {e}"]
    except DATA_ERRORS as e:
        return [f"Error in search_by_first_letter: {e}"]

    return recipe_ids


@mcp.tool()
def get_random_recipe() -> str:
    """
    Get a random recipe from TheMealDB.

    Returns:
        JSON string with random recipe information
    """
    try:
        meals = _fetch_meals("random.php")
        if not meals:
            return "No random recipe found"
        meal = meals[0]
        recipe_info: JSONDict = {"id": meal.get("idMeal"), **_parse_meal(meal)}
    except requests.RequestException as e:
        return f"Error getting random recipe: {e}"
    except DATA_ERRORS as e:
        return f"Error in get_random_recipe: {e}"

    return json.dumps(recipe_info, indent=2)


@mcp.tool()
def test_filesystem() -> str:
    """Test basic filesystem operations"""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.json"
            test_data = {"test": "data", "status": "working", "platform": sys.platform}
            _save_json(test_file, test_data)
            loaded_data = _load_json(test_file)
    except DATA_ERRORS as e:
        return f"Filesystem test FAILED: {e}"

    return f"Filesystem test PASSED on {sys.platform}: {loaded_data}"


@mcp.tool()
def get_system_info() -> str:
    """Get system and directory information for debugging"""
    recipes_dir_exists = RECIPES_DIR.exists()
    info: JSONDict = {
        "platform": sys.platform,
        "python_version": sys.version,
        "script_directory": str(SCRIPT_DIR),
        "recipes_directory": str(RECIPES_DIR),
        "recipes_dir_exists": recipes_dir_exists,
        "recipes_dir_is_writable": recipes_dir_exists
        and os.access(RECIPES_DIR, os.W_OK),
        "current_working_directory": str(Path.cwd()),
    }
    return json.dumps(info, indent=2)


# ==================== RESOURCES ====================
# Resources provide read-only access to data


@mcp.resource("recipes://cuisines")
def get_available_cuisines() -> str:
    """
    List all available cuisine folders in the recipes directory.

    This resource provides a simple list of all available cuisine/dish folders
    that contain saved recipe information.
    """
    folders = [d.name for d in _collection_dirs()]

    # Create a simple markdown list
    content = "# Available Recipe Collections\n\n"
    if folders:
        content += f"Found **{len(folders)}** recipe collections:\n\n"
        for folder in folders:
            display_name = folder.replace("_", " ").title()
            content += f"- **{display_name}** (folder: `{folder}`)\n"
        content += (
            "\n📖 Use `recipes://<folder_name>` to access recipes in that collection.\n"
        )
        content += "\n💡 Example: `recipes://italian` or `recipes://pasta`\n"
    else:
        content += "No recipe collections found. Search for some recipes first!\n"

    return content


@mcp.resource("recipes://{cuisine}")
def get_cuisine_recipes(cuisine: str) -> str:
    """
    Get detailed information about recipes in a specific cuisine/dish collection.

    Args:
        cuisine: The cuisine/dish folder name to retrieve recipes for
    """
    recipes_file = RECIPES_DIR / cuisine / "recipes_info.json"

    if not recipes_file.exists():
        return f"# No recipes found for: {cuisine}\n\nTry searching for recipes on this topic first."

    try:
        recipes_data: dict[str, JSONDict] = _load_json(recipes_file)
    except json.JSONDecodeError:
        return f"# Error reading recipes data for {cuisine}\n\nThe recipes data file is corrupted."
    except OSError as e:
        return f"# Error accessing {cuisine} recipes\n\nError: {e}"

    # Create markdown content with recipe details
    display_name = cuisine.replace("_", " ").title()
    content = f"# {display_name} Recipe Collection\n\n"
    content += f"📚 Total recipes: **{len(recipes_data)}**\n\n"

    for recipe_id, recipe_info in recipes_data.items():
        content += f"## 🍽️ {recipe_info.get('name', 'Unknown')}\n"
        content += f"- **Recipe ID**: `{recipe_id}`\n"
        content += f"- **Cuisine**: {recipe_info.get('cuisine', 'Unknown')}\n"
        content += f"- **Category**: {recipe_info.get('category', 'Unknown')}\n"

        # Add ingredients summary
        ingredients: list[dict[str, str]] = recipe_info.get("ingredients", [])
        if ingredients:
            main = ", ".join(ing["ingredient"] for ing in ingredients[:5])
            content += f"- **Main Ingredients**: {main}"
            if len(ingredients) > 5:
                content += f" (+{len(ingredients) - 5} more)"
            content += "\n"

        # Add links if available
        if recipe_info.get("image_url"):
            content += f"- **Image**: [View Recipe Photo]({recipe_info['image_url']})\n"
        if recipe_info.get("youtube_url"):
            content += (
                f"- **Video**: [Watch on YouTube]({recipe_info['youtube_url']})\n"
            )

        # Add truncated instructions
        instructions: str = (
            recipe_info.get("instructions") or "No instructions available"
        )
        if len(instructions) > 300:
            content += f"\n### 📋 Instructions Preview\n{instructions[:300]}...\n\n"
        else:
            content += f"\n### 📋 Instructions\n{instructions}\n\n"

        content += "---\n\n"

    if recipes_data:
        first_id = next(iter(recipes_data))
        content += f"\n💡 **Tip**: Use `get_recipe_details('{first_id}')` to get full details for any recipe.\n"

    return content


@mcp.resource("recipes://meal-plans")
def get_available_meal_plans() -> str:
    """
    List all available meal plans that have been created.

    This resource provides access to saved meal plans.
    """
    meal_plans_dir = RECIPES_DIR / "meal_plans"

    if not meal_plans_dir.exists():
        return "# No Meal Plans Found\n\nCreate your first meal plan using the `create_meal_plan` tool!"

    content = "# 📅 Available Meal Plans\n\n"
    plan_lines: list[str] = []
    for plan_file in meal_plans_dir.glob("*.json"):
        try:
            plan_data: JSONDict = _load_json(plan_file)
        except DATA_ERRORS as e:
            logger.warning("Skipping unreadable meal plan %s: %s", plan_file, e)
            continue
        created = str(plan_data.get("created_date", "Unknown"))
        plan_lines.append(
            f"## 🍽️ {plan_data.get('plan_name', 'Unknown Plan')}\n"
            f"- **Recipes**: {plan_data.get('total_recipes', 0)} dishes\n"
            f"- **Created**: {created[:10] if 'T' in created else created}\n"
            f"- **File**: `{plan_file.name}`\n\n"
        )

    if plan_lines:
        content += f"Found **{len(plan_lines)}** meal plans:\n\n"
        content += "".join(plan_lines)
    else:
        content += "No meal plans found. Create your first meal plan!\n"

    return content


@mcp.resource("recipes://stats")
def get_recipe_statistics() -> str:
    """
    Get overall statistics about the recipe collection.

    This resource provides insights into the recipe database.
    """
    total_recipes = 0
    total_collections = 0
    cuisines: Counter[str] = Counter()
    categories: Counter[str] = Counter()

    # Count recipes by cuisine and category
    for collection_dir in _collection_dirs():
        recipes_file = collection_dir / "recipes_info.json"
        try:
            recipes_data: dict[str, JSONDict] = _load_json(recipes_file)
        except DATA_ERRORS as e:
            logger.warning("Skipping unreadable collection %s: %s", recipes_file, e)
            continue

        total_collections += 1
        total_recipes += len(recipes_data)
        for recipe in recipes_data.values():
            cuisines[str(recipe.get("cuisine", "Unknown"))] += 1
            categories[str(recipe.get("category", "Unknown"))] += 1

    # Count meal plans
    meal_plans_dir = RECIPES_DIR / "meal_plans"
    meal_plans = (
        len(list(meal_plans_dir.glob("*.json"))) if meal_plans_dir.exists() else 0
    )

    # Create markdown content
    content = "# 📊 Recipe Collection Statistics\n\n"
    content += "## 📈 Overview\n"
    content += f"- **Total Recipes**: {total_recipes}\n"
    content += f"- **Recipe Collections**: {total_collections}\n"
    content += f"- **Meal Plans**: {meal_plans}\n\n"

    if cuisines:
        content += "## 🌍 Top Cuisines\n"
        for cuisine, count in cuisines.most_common(10):
            content += f"- **{cuisine}**: {count} recipes\n"
        content += "\n"

    if categories:
        content += "## 🍽️ Recipe Categories\n"
        for category, count in categories.most_common(10):
            content += f"- **{category}**: {count} recipes\n"
        content += "\n"

    content += (
        "💡 **Tip**: Explore specific collections using `recipes://<cuisine_name>`\n"
    )

    return content


# ==================== PROMPTS ====================
# Prompts provide pre-defined templates for common recipe-related tasks


@mcp.prompt()
def generate_recipe_search_prompt(cuisine_type: str, num_recipes: int = 5) -> str:
    """Generate a prompt for Claude to find and discuss recipes from a specific cuisine."""
    return f"""Search for {num_recipes} recipes from '{cuisine_type}' cuisine using the search_recipes tool. Follow these instructions:

1. First, search for recipes using search_recipes(dish_name='{cuisine_type}', max_results={num_recipes})

2. For each recipe found, extract and organize the following information:
   - Recipe name and ID
   - Cuisine origin and category
   - Key ingredients and their quantities
   - Cooking time and difficulty level
   - Cooking methods and techniques used
   - Nutritional highlights or dietary considerations
   - Cultural significance or traditional context

3. Provide a comprehensive culinary analysis that includes:
   - Overview of {cuisine_type} cuisine characteristics
   - Common ingredients and flavor profiles across the recipes
   - Traditional cooking techniques and methods
   - Regional variations or modern adaptations
   - Most authentic or representative dishes

4. Organize your findings in a clear, structured format with headings and bullet points for easy readability.

Please present both detailed information about each recipe and a high-level understanding of {cuisine_type} culinary traditions."""


@mcp.prompt()
def generate_meal_planning_prompt(
    meal_type: str, people_count: int = 4, dietary_restrictions: str = "none"
) -> str:
    """Generate a prompt for Claude to create a comprehensive meal plan."""
    return f"""Create a detailed {meal_type} meal plan for {people_count} people with dietary considerations: '{dietary_restrictions}'. Follow these instructions:

1. Search for appropriate recipes using the available search tools, considering:
   - Meal type: {meal_type}
   - Serving size: {people_count} people
   - Dietary restrictions: {dietary_restrictions}

2. For each selected recipe, analyze:
   - Preparation and cooking time
   - Ingredient availability and cost
   - Nutritional balance and dietary compliance
   - Cooking skill level required
   - Equipment and tools needed

3. Create a comprehensive meal planning guide that includes:
   - Complete shopping list with quantities
   - Preparation timeline and cooking schedule
   - Kitchen organization and mise en place tips
   - Nutritional breakdown and balance
   - Cost estimation and budget considerations
   - Alternative ingredients for dietary substitutions

4. Provide practical meal planning advice:
   - Make-ahead preparation tips
   - Storage and leftover suggestions
   - Scaling recipes up or down
   - Time-saving techniques

5. Use create_meal_plan() to save your final meal plan with an appropriate name.

Present your meal plan in a clear, actionable format that a home cook can easily follow."""


@mcp.prompt()
def generate_cooking_lesson_prompt(
    skill_level: str, technique_focus: str, cuisine_style: str = "any"
) -> str:
    """Generate a prompt for Claude to create a structured cooking lesson."""
    return f"""Design a comprehensive cooking lesson for a {skill_level} level cook focusing on '{technique_focus}' technique within {cuisine_style} cuisine. Follow these instructions:

1. Search for appropriate recipes that demonstrate the {technique_focus} technique using search_recipes

2. Structure your lesson to include:
   - Technique explanation and theory
   - Equipment and tools required
   - Step-by-step technique demonstration
   - Common mistakes and how to avoid them
   - Quality indicators and success markers
   - Troubleshooting guide

3. Select recipes that progressively build skills:
   - Start with basic {technique_focus} applications
   - Progress to intermediate variations
   - Include advanced applications for skill building
   - Provide practice exercises and variations

4. Create educational content covering:
   - Historical and cultural context of the technique
   - Science behind the cooking method
   - Ingredient selection and preparation
   - Temperature control and timing
   - Visual and sensory cues for doneness

5. Provide learning objectives and assessment:
   - Clear learning goals for the lesson
   - Practice recommendations
   - Self-assessment criteria
   - Next steps for skill progression

Present your lesson in a structured, educational format suitable for {skill_level} level cooks learning {technique_focus}."""


@mcp.prompt()
def generate_ingredient_exploration_prompt(
    main_ingredient: str, cooking_styles: str = "diverse", num_recipes: int = 6
) -> str:
    """Generate a prompt for Claude to explore and analyze recipes featuring a specific ingredient."""
    return f"""Conduct a comprehensive exploration of '{main_ingredient}' through {num_recipes} diverse recipes with {cooking_styles} cooking styles. Follow these instructions:

1. Search for recipes featuring {main_ingredient} using available search tools to find {num_recipes} different preparations

2. For each recipe, analyze the ingredient usage:
   - How {main_ingredient} is prepared and processed
   - Cooking methods applied to {main_ingredient}
   - Flavor pairings and complementary ingredients
   - Cultural or regional preparation differences
   - Nutritional contributions and benefits
   - Texture and appearance transformations

3. Create a comprehensive ingredient profile including:
   - Botanical/biological background of {main_ingredient}
   - Nutritional composition and health benefits
   - Seasonal availability and sourcing tips
   - Storage methods and shelf life
   - Quality selection criteria
   - Common varieties and substitutions

4. Provide culinary technique analysis:
   - Best cooking methods for {main_ingredient}
   - Temperature and timing considerations
   - Preparation techniques and knife skills
   - Flavor enhancement strategies
   - Common cooking mistakes to avoid

5. Synthesize your findings into:
   - Versatility assessment of {main_ingredient}
   - Recipe recommendations for different skill levels
   - Menu planning suggestions
   - Cost-effective usage tips
   - Creative preparation ideas

Present your exploration as an educational ingredient guide that helps cooks understand and maximize the potential of {main_ingredient}."""


@mcp.prompt()
def generate_cultural_cuisine_prompt(
    cuisine_name: str, cultural_context: str = "traditional", num_recipes: int = 5
) -> str:
    """Generate a prompt for Claude to explore the cultural and historical aspects of a cuisine."""
    return f"""Explore the cultural heritage and culinary traditions of {cuisine_name} cuisine from a {cultural_context} perspective through {num_recipes} representative recipes. Follow these instructions:

1. Search for authentic {cuisine_name} recipes using search_recipes and get_recipe_details

2. For each recipe, research and document:
   - Historical origins and cultural significance
   - Traditional preparation methods and rituals
   - Regional variations and family traditions
   - Social and ceremonial context
   - Seasonal and festival associations
   - Evolution and modern adaptations

3. Provide comprehensive cultural analysis including:
   - Geographic influences on {cuisine_name} cuisine
   - Historical trade routes and ingredient introductions
   - Religious and cultural dietary influences
   - Social hierarchy and food accessibility
   - Gender roles and cooking traditions
   - Celebration and hospitality customs

4. Examine culinary techniques and philosophy:
   - Traditional cooking methods and equipment
   - Flavor balance and seasoning principles
   - Ingredient sourcing and preservation methods
   - Meal structure and eating customs
   - Food presentation and aesthetic principles

5. Create educational content covering:
   - Key ingredients native to the region
   - Essential cooking techniques and skills
   - Cultural etiquette and dining customs
   - Modern influence and fusion adaptations
   - Preservation of culinary heritage

Present your exploration as a cultural culinary journey that respects and celebrates the heritage of {cuisine_name} cuisine while providing practical cooking knowledge."""


if __name__ == "__main__":
    # Bind to all interfaces so the server is reachable when deployed
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
