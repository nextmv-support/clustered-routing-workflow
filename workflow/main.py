import colorsys
import glob
import json
import nextmv
import nextmv.cloud
from nextpipe import FlowSpec, app, foreach, join, needs, step
import pandas as pd

options = nextmv.Options(
    nextmv.Option("input", str, "inputs/", "Path to input dir.", False),
    nextmv.Option("output", str, "outputs/solutions/", "Path to output dir.", False),
    nextmv.Option("assets", str, "outputs/assets/", "Path to asset dir.", False),
)


# >>> Workflow definition
class Flow(FlowSpec):
    @app(app_id="cluster-routing")
    @step
    def cluster():
        """Split the orders using the cluster model."""
        pass

    @needs(predecessors=[cluster])
    @foreach()
    @step
    def transform(result_path: str):
        """Transforms the result for nextroute."""
        # Convert all CSV files in result_path to nextroute format (dict/JSON)
        routing_inputs = []
        for file_path in glob.glob(f"{result_path}/*.csv"):



    @app(app_id="routing-nextroute")
    @needs(predecessors=[transform])
    @step
    def routing():
        """Runs the routing application."""
        pass

    @needs(predecessors=[routing])
    @join()
    @step
    def merge_output(result: list[dict]):
        """Merge the outputs and convert them to CSV."""
        pass


def main():
    flow = Flow("DecisionFlow", options.input)
    flow.run()


if __name__ == "__main__":
    main()


# # Write cluster asset for visualization
#     cluster_asset_data = cluster_asset(data)
#     with open("assets.json", "w") as f:
#         json.dump(cluster_asset_data, f, indent=2)

def get_color(value: float, saturation: float = 0.8, brightness: float = 0.8) -> str:
    """
    Maps a float value in [0, 1] to a hex color code from blue to red.
    """
    h = (1.0 - value) * 0.66  # Hue from blue (0.66) to red (0.0)
    r, g, b = colorsys.hsv_to_rgb(h, saturation, brightness)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def cluster_asset(clustered_stops: pd.DataFrame) -> dict:
    """
    Create a visualization asset for the clustered stops. A simple GeoJSON structure
    with colored points based on cluster assignments.
    """
    features = []
    unique_clusters = sorted(clustered_stops["cluster"].unique())
    cluster_id_to_color = {cid: get_color(i / (len(unique_clusters) - 1)) for i, cid in enumerate(unique_clusters)}

    for _, row in clustered_stops.iterrows():
        feature = {
            "id": row["id"],
            "type": "Feature",
            "properties": {
                "style": {
                    "color": cluster_id_to_color[row["cluster"]],
                },
                "metadata": [
                    {"key": "id", "value": row["id"]},
                    {"key": "cluster", "value": row["cluster"]},
                ],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [row["lon"], row["lat"]],
            },
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    return {
        "assets": {
            "name": "clustered_stops",
            "content": geojson,
            "content_type": "json",
            "visual": {"schema": "geojson", "type": "custom-tab", "label": "Clusters"},
        }
    }
