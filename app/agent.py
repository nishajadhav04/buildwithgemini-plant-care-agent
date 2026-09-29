# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
from typing import Optional
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from dotenv import load_dotenv
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

try:
    from .a2ui_utils import a2ui_callback
except ImportError:
    from app.a2ui_utils import a2ui_callback

load_dotenv()



# Hardcoded GCP Project ID and Cloud Storage Bucket Name
PROJECT_ID = "qwiklabs-gcp-03-04a064262bb6"
BUCKET_NAME = "plant-care-assets-qwiklabs-gcp-03-04a064262bb6"

# Load Agent Engine resource name / Memory Bank ID from deployment_metadata.json
_metadata_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
_agent_engine_resource_name = None
if os.path.exists(_metadata_path):
    try:
        with open(_metadata_path, "r", encoding="utf-8") as _f:
            _meta = json.load(_f)
            _agent_engine_resource_name = _meta.get("remote_agent_runtime_id")
    except Exception:
        pass

_memory_bank_id = _agent_engine_resource_name.split("/")[-1] if _agent_engine_resource_name else "6869341831042170880"

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=_agent_engine_resource_name
)


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract durable memories after each turn and save to Memory Bank."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None



def memory_service_builder():
    """Builds VertexAiMemoryBankService instance using configured Memory Bank ID."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-east1",
        agent_engine_id=_memory_bank_id,
    )





def _get_firestore_client():
    return firestore.Client(project=PROJECT_ID)


def list_plants(search_query: str = "") -> list[dict]:
    """Lists houseplant inventory from Firestore database with optional search filtering.

    Args:
        search_query: Optional search keyword to filter plants by name or species.

    Returns:
        List of plant dictionaries containing id, name, species, watering frequency, sunlight, and price.
    """
    db = _get_firestore_client()
    docs = db.collection("plants").stream()
    plants = []
    query_lower = search_query.lower()
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        if search_query:
            name = str(data.get("name", "")).lower()
            species = str(data.get("species", "")).lower()
            if query_lower in name or query_lower in species:
                plants.append(data)
        else:
            plants.append(data)
    return plants


def get_plant_details(plant_id: str) -> dict:
    """Gets detailed information and care instructions for a specific houseplant by ID.

    Args:
        plant_id: The document ID of the plant (e.g. 'p1', 'p2').

    Returns:
        Plant document data dictionary or error message if not found.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("plants").document(plant_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return {"error": f"Plant with ID '{plant_id}' not found."}


def add_plant(
    name: str,
    species: str,
    watering_frequency_days: int,
    sunlight_requirement: str,
    care_level: str,
    price_usd: float,
    description: str = "",
) -> dict:
    """Adds a new houseplant to the Firestore inventory catalog.

    Args:
        name: Common name of the plant (e.g. 'Monstera Deliciosa').
        species: Botanical/scientific species name (e.g. 'Monstera deliciosa').
        watering_frequency_days: Recommended interval in days between waterings.
        sunlight_requirement: Sunlight requirement (e.g. 'Bright indirect light').
        care_level: Difficulty level ('Easy', 'Intermediate', 'Advanced').
        price_usd: Price in USD.
        description: Brief description of plant attributes.

    Returns:
        Dictionary containing success status and created plant document ID.
    """
    db = _get_firestore_client()
    plants_ref = db.collection("plants")
    new_doc_ref = plants_ref.document()
    plant_data = {
        "id": new_doc_ref.id,
        "name": name,
        "species": species,
        "watering_frequency_days": watering_frequency_days,
        "sunlight_requirement": sunlight_requirement,
        "care_level": care_level,
        "price_usd": price_usd,
        "description": description,
        "in_stock": True,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    new_doc_ref.set(plant_data)
    return {"status": "success", "plant": plant_data}


def update_plant_care(
    plant_id: str,
    watering_frequency_days: Optional[int] = None,
    sunlight_requirement: Optional[str] = None,
    care_level: Optional[str] = None,
) -> dict:
    """Updates care parameters for an existing plant in Firestore.

    Args:
        plant_id: ID of the plant document to update.
        watering_frequency_days: Updated watering interval in days.
        sunlight_requirement: Updated sunlight needs description.
        care_level: Updated care difficulty level.

    Returns:
        Updated document status dictionary.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("plants").document(plant_id)
    doc = doc_ref.get()
    if not doc.exists:
        return {"error": f"Plant with ID '{plant_id}' not found."}

    updates = {}
    if watering_frequency_days is not None:
        updates["watering_frequency_days"] = watering_frequency_days
    if sunlight_requirement is not None:
        updates["sunlight_requirement"] = sunlight_requirement
    if care_level is not None:
        updates["care_level"] = care_level

    if updates:
        doc_ref.update(updates)

    return {"status": "updated", "plant_id": plant_id, "updated_fields": updates}


def calculate_watering_schedule(
    plant_id: str,
    temperature_f: int = 70,
    humidity_percent: int = 50,
) -> dict:
    """Calculates an adjusted watering schedule for a plant based on room temperature and humidity.

    Args:
        plant_id: Document ID of the plant in Firestore (e.g. 'p1', 'p2').
        temperature_f: Current room temperature in Fahrenheit (°F).
        humidity_percent: Relative humidity percentage (%).

    Returns:
        Dictionary containing base and adjusted watering frequency in days and care recommendations.
    """
    plant = get_plant_details(plant_id)
    if "error" in plant:
        return plant

    base_days = plant.get("watering_frequency_days", 7)
    adjusted_days = base_days

    if temperature_f > 78:
        adjusted_days -= 2
    elif temperature_f < 65:
        adjusted_days += 2

    if humidity_percent < 40:
        adjusted_days -= 1
    elif humidity_percent > 65:
        adjusted_days += 1

    adjusted_days = max(2, adjusted_days)

    return {
        "plant_id": plant_id,
        "plant_name": plant.get("name"),
        "base_watering_frequency_days": base_days,
        "adjusted_watering_frequency_days": adjusted_days,
        "temperature_f": temperature_f,
        "humidity_percent": humidity_percent,
        "recommendation": (
            f"In a {temperature_f}°F room with {humidity_percent}% humidity, water {plant.get('name')} "
            f"every {adjusted_days} days (base schedule is every {base_days} days)."
        ),
    }


import os
import json
import urllib.parse
import urllib.request


def fetch_plant_botany_info(plant_name: str) -> dict:
    """Fetches real botanical research data, description, species origins, and image URL for a plant species.

    Args:
        plant_name: Name of the plant or species (e.g. 'Monstera deliciosa', 'Ficus lyrata', 'Snake plant').

    Returns:
        Dictionary containing botanical title, summary extract, thumbnail image URL, and reference link.
    """
    api_key = os.environ.get("PERENUAL_API_KEY")
    if api_key:
        try:
            encoded_q = urllib.parse.quote(plant_name)
            url = f"https://perenual.com/api/species-list?key={api_key}&q={encoded_q}"
            req = urllib.request.Request(url, headers={"User-Agent": "PlantCareAgent/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("data"):
                    first_item = data["data"][0]
                    return {
                        "title": first_item.get("common_name", plant_name),
                        "scientific_name": first_item.get("scientific_name", []),
                        "cycle": first_item.get("cycle"),
                        "watering": first_item.get("watering"),
                        "sunlight": first_item.get("sunlight"),
                        "thumbnail_url": first_item.get("default_image", {}).get("thumbnail"),
                    }
        except Exception:
            pass

    try:
        formatted_name = urllib.parse.quote(plant_name.strip().replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{formatted_name}"
        req = urllib.request.Request(url, headers={"User-Agent": "PlantCareAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "title": data.get("title", plant_name),
                "description": data.get("description", "Botanical species"),
                "extract": data.get("extract", "No extract available."),
                "thumbnail_url": data.get("thumbnail", {}).get("source"),
                "content_url": data.get("content_urls", {}).get("desktop", {}).get("page"),
            }
    except Exception as e:
        return {"error": f"Unable to fetch botanical info for '{plant_name}': {str(e)}"}


def geocode_address(address: str) -> dict:
    """Converts a street address, city, or location name into geographic latitude and longitude coordinates.

    Args:
        address: Address or location string (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA' or 'San Francisco, CA').

    Returns:
        Dictionary containing formatted_address, latitude, and longitude.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY is not configured in environment."}

    try:
        encoded_address = urllib.parse.quote(address)
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "PlantCareAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                loc = result.get("geometry", {}).get("location", {})
                return {
                    "address": address,
                    "formatted_address": result.get("formatted_address"),
                    "location": {
                        "latitude": loc.get("lat"),
                        "longitude": loc.get("lng"),
                    },
                }
            return {"error": f"Geocoding failed for address '{address}': {data.get('status')}"}
    except Exception as e:
        return {"error": f"Failed to geocode address '{address}': {str(e)}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "florist",
    radius_meters: float = 5000.0,
) -> dict:
    """Finds nearby points of interest (e.g. florists, plant nurseries, parks, garden centers) using Places API (New).

    Args:
        latitude: Search center latitude.
        longitude: Search center longitude.
        place_type: Included place type (e.g. 'florist', 'park', 'store', 'shopping_mall').
        radius_meters: Radius in meters around the center location (default 5000m).

    Returns:
        Dictionary containing list of nearby places with name, formatted_address, location, and rating.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY is not configured in environment."}

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.rating,places.types",
    }
    payload = json.dumps({
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": float(radius_meters),
            }
        },
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = []
            for place in data.get("places", []):
                display_name = place.get("displayName", {}).get("text")
                results.append({
                    "name": display_name,
                    "address": place.get("formattedAddress"),
                    "location": place.get("location"),
                    "rating": place.get("rating"),
                    "types": place.get("types", []),
                })
            return {
                "latitude": latitude,
                "longitude": longitude,
                "place_type": place_type,
                "places": results,
            }
    except Exception as e:
        return {"error": f"Places search failed: {str(e)}"}


def generate_plant_image(
    prompt: str,
    tool_context: ToolContext,
    object_name: str = "generated_plant.jpeg",
) -> dict:
    """Generates an image of a plant using the gemini-3.1-flash-lite-image model in global region, saves it as an artifact, and uploads it to public Cloud Storage.

    Args:
        prompt: Description of the plant or botanical scene to generate (e.g. 'A lush Monstera Deliciosa in a ceramic pot').
        object_name: Filename/object key to save as artifact and in Cloud Storage (e.g. 'monstera_portrait.jpeg').

    Returns:
        Dictionary containing success status, public_url on Cloud Storage, artifact filename, and version.
    """
    try:
        genai_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
        )
        res = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"Generate a high quality realistic image of: {prompt}",
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
            for part in res.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or mime_type
                    break

        if not image_bytes:
            return {"error": "Failed to generate image bytes from model."}

        # 1. Save artifact using tool_context.save_artifact
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        artifact_version = tool_context.save_artifact(
            filename=object_name,
            artifact=image_part,
        )

        # 2. Upload to public Cloud Storage bucket and return public URL
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(object_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{object_name}"

        return {
            "status": "success",
            "public_url": public_url,
            "artifact_filename": object_name,
            "artifact_version": artifact_version,
        }
    except Exception as e:
        return {"error": f"Failed to generate and upload image: {str(e)}"}


def generate_plant_video(
    prompt: str,
    tool_context: ToolContext,
    object_name: str = "generated_plant_video.mp4",
) -> dict:
    """Generates a short video of a plant or botanical item using the gemini-omni-flash-preview model in global region, saves it as an artifact, and uploads it to public Cloud Storage.

    Args:
        prompt: Description of the plant or botanical scene to generate video for (e.g. 'A tropical Monstera plant leaf unfolding in a greenhouse').
        object_name: Filename/object key to save as artifact and in Cloud Storage (e.g. 'monstera_leaf.mp4').

    Returns:
        Dictionary containing success status, public_url on Cloud Storage, artifact filename, and version.
    """
    try:
        genai_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
        )
        res = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=f"Generate a short video of: {prompt}",
        )

        video_bytes = None
        mime_type = "video/mp4"

        if hasattr(res, "output_video") and res.output_video:
            out = res.output_video
            if getattr(out, "data", None):
                video_bytes = out.data
                mime_type = getattr(out, "mime_type", None) or mime_type
        if not video_bytes and getattr(res, "output", None):
            out = res.output
            if getattr(out, "data", None):
                video_bytes = out.data
                mime_type = getattr(out, "mime_type", None) or mime_type

        if not video_bytes:
            return {"error": "Failed to generate video bytes from model."}

        # 1. Save artifact using tool_context.save_artifact
        video_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        artifact_version = tool_context.save_artifact(
            filename=object_name,
            artifact=video_part,
        )

        # 2. Upload to public Cloud Storage bucket and return public URL
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(object_name)
        blob.upload_from_string(video_bytes, content_type=mime_type)
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{object_name}"

        return {
            "status": "success",
            "public_url": public_url,
            "artifact_filename": object_name,
            "artifact_version": artifact_version,
        }
    except Exception as e:
        return {"error": f"Failed to generate and upload video: {str(e)}"}


def get_weather(query: str) -> str:
    """Simulates a web search. Use it to get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city or query to get current time for.

    Returns:
        A string with current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are the Plant Care & Marketplace Assistant. "
        "You help users manage houseplant inventory, look up plant details, "
        "add new plants, update care instructions, calculate custom watering schedules based on environment, "
        "look up botanical research and species background using fetch_plant_botany_info, "
        "convert location addresses to coordinates with geocode_address, "
        "find nearby plant nurseries or florists with find_nearby_places, "
        "generate realistic plant images with generate_plant_image, "
        "generate short plant videos with generate_plant_video using Gemini Omni model, "
        "execute python code in sandbox for complex calculations when needed, "
        "remember user preferences, health conditions, and all user allergies (e.g., plant allergies, pollen sensitivities, pet/human toxicity, sap irritants) across sessions using Memory Bank, "
        "and proactively check and warn against any plants or recommendations that could trigger the user's allergies."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property (\'h1\', \'h2\', \'body\') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or \'kind\'/\'data\'/\'metadata\' objects."
    ),
    include_schema=False,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        list_plants,
        get_plant_details,
        add_plant,
        update_plant_care,
        calculate_watering_schedule,
        fetch_plant_botany_info,
        geocode_address,
        find_nearby_places,
        generate_plant_image,
        generate_plant_video,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)




app = App(
    root_agent=root_agent,
    name="app",
)






