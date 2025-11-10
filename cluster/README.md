# Split stops into clusters

This model takes a set of stops and splits them into `k` clusters.

The input is read from a `stops.csv` file (usually located in `./inputs/` dir - see example). The outputs are multiple CSV files (one per cluster) written to the `./outputs/` directory.

## Usage

Locally:

```bash
python main.py --clusters 5
```

Remotely (Nextmv Cloud):

```bash
nextmv app create -a cluster-routing -n "Cluster Routing" -d "An app that clusters stops for routing"
nextmv app push -a cluster-routing
nextmv app run -a cluster-routing -i inputs/ -o 'clusters=5'
```
