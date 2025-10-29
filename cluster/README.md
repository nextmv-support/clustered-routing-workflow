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
nextmv app push -a <app-id>
nextmv app run -a <app-id> -i inputs/ -o 'clusters=5'
```
