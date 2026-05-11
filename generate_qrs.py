import qrcode
import json

# Fetch your layout_plan to know which shelves exist
with open("layout.json", "r") as f:
    data = json.load(f)

# Extract shelf IDs (handling your specific nested structure)
shelf_ids = []
for block in data:
    for shelf in block["layout_plan"]:
        shelf_ids.append(shelf["shelf_id"])

def create_shelf_qrs(ids):
    for sid in ids:
        # The QR stores a URL or a JSON string the React app recognizes
        # Example: https://your-app-url.com/shelf/15
        qr_data = f"SHELF_{sid}" 
        qr = qrcode.make(qr_data)
        qr.save(f"shelf_qr_{sid}.png")
        print(f"✅ Generated QR for Shelf {sid}")

create_shelf_qrs(shelf_ids)