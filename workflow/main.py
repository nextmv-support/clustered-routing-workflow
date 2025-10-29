import colorsys
import datetime
import glob
import json
import os
from typing import Any

import nextmv
import nextmv.cloud
import pandas as pd
import pytz
from nextpipe import FlowSpec, app, foreach, join, needs, step

options = nextmv.Options(
    # IO related options
    nextmv.Option("input", str, "inputs/", "Path to input dir.", False),
    nextmv.Option("output", str, "outputs/solutions/", "Path to output dir.", False),
    nextmv.Option("statistics", str, "outputs/statistics/", "Path to statistics dir.", False),
    nextmv.Option("assets", str, "outputs/assets/", "Path to asset dir.", False),
    # Clustering options
    nextmv.Option("cluster_count", int, 5, "Number of clusters to create.", False),
    nextmv.Option("cluster_duration", int, 300, "Max duration for clustering (in seconds).", False),
    nextmv.Option("cluster_provider", str, "SCIP", "Solver provider for clustering.", False),
    # Vehicle configuration
    nextmv.Option("vehicle_max_duration", int, 7200, "Max duration per vehicle in seconds.", False),
    nextmv.Option("vehicle_count", int, 5, "Number of vehicles available.", False),
)


# >>> Workflow definition
class Flow(FlowSpec):
    @app(
        app_id="cluster-routing",
        options={
            "clusters": options.cluster_count,
            "duration": options.cluster_duration,
            "provider": options.cluster_provider,
        },
        full_result=True,
    )
    @step
    def cluster():
        """Split the orders using the cluster model."""
        pass

    @needs(predecessors=[cluster])
    @foreach()
    @step
    def transform(result: nextmv.cloud.RunResult):
        """Transforms the result for nextroute."""
        # Shift start is tomorrow at 8am
        shift_start = datetime.datetime.now(pytz.timezone("UTC")).replace(
            hour=8, minute=0, second=0, microsecond=0
        ) + datetime.timedelta(days=1)
        # Convert all CSV files in result_path to nextroute format (dict/JSON)
        routing_inputs = []
        for file_path in glob.glob(f"{result.output}/*.csv"):
            df = pd.read_csv(file_path)
            routing_input = {
                "defaults": {
                    "vehicles": {
                        "start_time": shift_start.isoformat(),
                        "max_duration": options.vehicle_max_duration,
                        "speed": 10,
                    },
                },
                "vehicles": [{"id": f"vehicle_{i}"} for i in range(options.vehicle_count)],
                "stops": [],
            }
            for _, row in df.iterrows():
                stop = {
                    "id": row["id"],
                    "location": {"lat": float(row["lat"]), "lon": float(row["lon"])},
                }
                routing_input["stops"].append(stop)
            routing_inputs.append(routing_input)
        return routing_inputs

    @app(app_id="routing-nextroute")
    @needs(predecessors=[transform])
    @step
    def route():
        """Runs the routing application."""
        pass

    @needs(predecessors=[route])
    @join()
    @step
    def merge_output(result: list[list[dict[str, Any]]]):
        """Merge the outputs and convert them to CSV."""
        routes, unplanned = [], []
        for i, routing_result in enumerate(result):
            routing_result = routing_result[0]  # Unwrap from list (only one predecessor)
            for stop in routing_result.get("solutions", [])[-1].get("unplanned", []):
                unplanned.append(
                    {
                        "id": stop["id"],
                        "lat": stop["location"]["lat"],
                        "lon": stop["location"]["lon"],
                    }
                )
            for vehicle in routing_result.get("solutions", [])[-1].get("vehicles", []):
                for stop in vehicle.get("route", []):
                    routes.append(
                        {
                            "vehicle_id": vehicle["id"],
                            "stop_id": stop["stop"]["id"],
                            "cluster": i,
                            "lat": stop["stop"]["location"]["lat"],
                            "lon": stop["stop"]["location"]["lon"],
                            "arrival_time": stop.get("arrival_time", None),
                            "start_time": stop.get("start_time", None),
                            "end_time": stop.get("end_time", None),
                            "cumulative_travel_duration": stop.get("cumulative_travel_duration", None),
                            "cumulative_travel_distance": stop.get("cumulative_travel_distance", None),
                        }
                    )

        # Write solutions
        routes_df = pd.DataFrame(routes)
        unplanned_df = pd.DataFrame(unplanned)
        os.makedirs(options.output, exist_ok=True)
        routes_df.to_csv(f"{options.output}/routes.csv", index=False)
        unplanned_df.to_csv(f"{options.output}/unplanned.csv", index=False)

        # Return result for subsequent steps
        return routes_df, unplanned_df

    @needs(predecessors=[cluster, route])
    @join()
    @step
    def collect_statistics(results: list[tuple[nextmv.cloud.RunResult, list[dict[str, Any]]]]):
        """Prepare overall statistics."""
        stats = {}
        # Simply relay cluster statistics as they are already scalar values
        cluster_stats = results[0][0].metadata.statistics
        if cluster_stats:
            stats.update(cluster_stats.get("result", {}).get("custom", {}))
        # Aggregate routing statistics
        total_unplanned_stops = 0
        total_vehicles_used = 0
        total_value = 0
        for routing_result in results:
            routing_result = routing_result[1]  # Unwrap from list (only one predecessor)
            routing_stats = routing_result.get("statistics", {}).get("result", {}).get("custom", {})
            total_unplanned_stops += routing_stats.get("unplanned_stops", 0)
            total_vehicles_used += routing_stats.get("activated_vehicles", 0)
            total_value += routing_result.get("statistics", {}).get("result", {}).get("value", 0)
        stats |= {
            "unplanned_stops": total_unplanned_stops,
            "activated_vehicles": total_vehicles_used,
            "value": total_value,
        }

        # Write solutions
        os.makedirs(options.statistics, exist_ok=True)
        with open(f"{options.statistics}/statistics.json", "w") as f:
            json.dump({"statistics": {"schema": "v1", "result": {"custom": stats}}}, f, indent=2)

    @needs(predecessors=[merge_output])
    @step
    def write_assets(result: tuple[pd.DataFrame, pd.DataFrame]):
        """Write visualization assets for the clustered stops."""
        clustered_stops_df, _ = result
        os.makedirs(options.assets, exist_ok=True)
        cluster_asset_data = Flow.cluster_asset(clustered_stops_df)
        with open(f"{options.assets}/assets.json", "w") as f:
            json.dump(cluster_asset_data, f, indent=2)

    @staticmethod
    def get_color(value: float, saturation: float = 0.8, brightness: float = 0.8) -> str:
        """
        Maps a float value in [0, 1] to a hex color code from blue to red.
        """
        h = (1.0 - value) * 0.66  # Hue from blue (0.66) to red (0.0)
        r, g, b = colorsys.hsv_to_rgb(h, saturation, brightness)
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

    @staticmethod
    def cluster_asset(clustered_stops: pd.DataFrame) -> dict:
        """
        Create a visualization asset for the clustered stops. A simple GeoJSON structure
        with colored points based on cluster assignments.
        """
        features = []
        unique_clusters = sorted(clustered_stops["cluster"].unique())
        cluster_id_to_color = {
            cid: Flow.get_color(i / (len(unique_clusters) - 1)) for i, cid in enumerate(unique_clusters)
        }

        for _, row in clustered_stops.iterrows():
            feature = {
                "id": row["stop_id"],
                "type": "Feature",
                "properties": {
                    "style": {
                        "color": cluster_id_to_color[row["cluster"]],
                    },
                    "metadata": [
                        {"key": "id", "value": row["stop_id"]},
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
            "assets": [
                {
                    "name": "clustered_stops",
                    "content": geojson,
                    "content_type": "json",
                    "visual": {"schema": "geojson", "type": "custom-tab", "label": "Clusters"},
                }
            ]
        }


def main():
    flow = Flow("DecisionFlow", options.input)
    flow.run()


if __name__ == "__main__":
    main()
