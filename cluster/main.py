import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from ortools.linear_solver import pywraplp
from sklearn.cluster import KMeans


def main():
    # Parse arguments
    args = parse_args()

    # Read input
    data = pd.read_csv("inputs/stops.csv")

    # Cluster stops
    cluster(data, args.clusters, args.provider, args.duration)

    # Write each cluster to separate file
    os.makedirs("solutions/", exist_ok=True)
    for cluster_id in range(args.clusters):
        cluster_data = data[data["cluster"] == cluster_id]
        cluster_data.to_csv(f"solutions/stops_cluster_{cluster_id}.csv", index=False)

    # Write statistics
    stats = get_statistics(data)
    print("Clustering statistics:")
    print(json.dumps(stats, indent=2))


def parse_args() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(description="Cluster and split routing input.")
    parser.add_argument(
        "--clusters",
        type=int,
        default=5,
        help="Number of clusters.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Max runtime duration (in seconds).",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="SCIP",
        help="Solver provider.",
    )
    return parser.parse_args()


def cluster(stops: pd.DataFrame, k: int, provider: str, duration: int) -> None:
    """
    Clusters the given stops into k balanced clusters using an integer programming
    approach.
    """
    # Convert stops to numpy array (columns: lat, lon)
    points = stops[["lat", "lon"]].to_numpy()
    n = points.shape[0]  # Number of points

    # Use K-Means++ to initialize centers
    kmeans = KMeans(n_clusters=k, init="k-means++", n_init=1)
    kmeans.fit(points)
    centers = kmeans.cluster_centers_

    # Calculate cost matrix using K-Means++ centers
    c = np.zeros((n, k))
    for j in range(k):
        c[:, j] = np.sum((points - centers[j]) ** 2, axis=1)  # Squared distance

    # Initialize the solver
    solver = pywraplp.Solver.CreateSolver(provider)
    solver.set_time_limit(duration * 1000)  # milliseconds

    if not solver:
        raise ValueError("Could not create solver.")

    # Decision variables: x[i][j] = 1 if point i is in cluster j
    x = {}
    for i in range(n):
        for j in range(k):
            x[(i, j)] = solver.IntVar(0, 1, f"x_{i}_{j}")

    # Objective: Minimize total within-cluster variance
    objective = solver.Objective()
    for i in range(n):
        for j in range(k):
            objective.SetCoefficient(x[(i, j)], c[i, j])
    objective.SetMinimization()

    # Constraints
    # 1. Each point assigned to exactly one cluster
    for i in range(n):
        solver.Add(solver.Sum(x[(i, j)] for j in range(k)) == 1)

    # 2. Cluster size balance
    L = n // k
    U = (n + k - 1) // k  # Ceiling division
    for j in range(k):
        solver.Add(solver.Sum(x[(i, j)] for i in range(n)) >= L)
        solver.Add(solver.Sum(x[(i, j)] for i in range(n)) <= U)

    # Solve the problem
    status = solver.Solve()

    # Extract cluster assignments
    cluster_assignments = [0] * n
    if status == pywraplp.Solver.OPTIMAL:
        for i in range(n):
            for j in range(k):
                if x[(i, j)].solution_value() > 0.5:
                    cluster_assignments[i] = j
    else:
        raise ValueError("No optimal solution found.")

    # Add cluster column to dataframe
    stops["cluster"] = cluster_assignments


def calculate_sse(df):
    """
    Cleans the 'lat' and 'lon' columns and then calculates the SSE.
    """
    # Convert to numeric (drop invalid entries)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df_cleaned = df.dropna(subset=["lat", "lon"])
    if len(df) != len(df_cleaned):
        print(f"⚠️ Removed {len(df) - len(df_cleaned)} row(s) with invalid geographic data.", file=sys.stderr)

    # Calculate SSE
    sse = 0.0
    centroids = df_cleaned.groupby("cluster").mean(numeric_only=True)[["lat", "lon"]]
    for cluster, centroid in centroids.iterrows():
        cluster_points = df_cleaned[df_cleaned["cluster"] == cluster]

        # Calculate squared Euclidean distance (
        squared_distances = (cluster_points["lat"] - centroid["lat"]) ** 2 + (
            cluster_points["lon"] - centroid["lon"]
        ) ** 2
        sse += squared_distances.sum()

    return sse


def get_statistics(df: pd.DataFrame) -> dict:
    """
    Get statistics about the clustering results.
    """
    stats = {}
    cluster_sizes = df["cluster"].value_counts()
    stats["num_clusters"] = cluster_sizes.shape[0]
    stats["min_cluster_size"] = float(cluster_sizes.min())
    stats["max_cluster_size"] = float(cluster_sizes.max())
    stats["avg_cluster_size"] = float(cluster_sizes.mean())
    stats["sse"] = float(calculate_sse(df))
    return stats


if __name__ == "__main__":
    main()
