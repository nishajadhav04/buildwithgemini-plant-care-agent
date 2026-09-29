import sys
from google.cloud import firestore

# Hardcode project ID to avoid project number resolution issues on Agent Platform
PROJECT_ID = "qwiklabs-gcp-03-04a064262bb6"

SEEDED_PLANTS = [
    {
        "id": "p1",
        "name": "Monstera Deliciosa",
        "species": "Monstera deliciosa",
        "watering_frequency_days": 7,
        "sunlight_requirement": "Bright indirect light",
        "care_level": "Easy",
        "price_usd": 35.00,
        "in_stock": True,
        "description": "Popular tropical houseplant with iconic split leaves."
    },
    {
        "id": "p2",
        "name": "Snake Plant",
        "species": "Dracaena trifasciata",
        "watering_frequency_days": 14,
        "sunlight_requirement": "Low to bright indirect light",
        "care_level": "Beginner / Very Easy",
        "price_usd": 25.00,
        "in_stock": True,
        "description": "Durable air-purifying plant tolerant of low light and infrequent watering."
    },
    {
        "id": "p3",
        "name": "Fiddle Leaf Fig",
        "species": "Ficus lyrata",
        "watering_frequency_days": 8,
        "sunlight_requirement": "Bright indirect light",
        "care_level": "Intermediate",
        "price_usd": 55.00,
        "in_stock": True,
        "description": "Stunning fiddle-shaped green leaves requiring consistent lighting and care."
    },
    {
        "id": "p4",
        "name": "Golden Pothos",
        "species": "Epipremnum aureum",
        "watering_frequency_days": 6,
        "sunlight_requirement": "Low to medium light",
        "care_level": "Easy",
        "price_usd": 18.00,
        "in_stock": True,
        "description": "Fast-growing trailing vine with variegated heart-shaped leaves."
    }
]

def seed():
    print(f"Connecting to Firestore with project_id={PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("plants")
    
    for plant in SEEDED_PLANTS:
        doc_id = plant["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(plant)
        print(f"✅ Seeded plant: {plant['name']} (ID: {doc_id})")
        
    print("\n🎉 Firestore database successfully seeded!")

if __name__ == "__main__":
    seed()
