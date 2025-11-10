import csv
import json

INPUT_FILE = "input.json"
OUTPUT_FILE = "input.csv"

# Read routing input json and convert to csv
with open(INPUT_FILE, "r") as f:
    routing_data = json.load(f)

# Write stops to CSV
with open(OUTPUT_FILE, "w", newline="") as csvfile:
    fieldnames = ["id", "lat", "lon"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for stop in routing_data["stops"]:
        writer.writerow({"id": stop["id"], "lat": stop["location"]["lat"], "lon": stop["location"]["lon"]})
