import nextmv
import nextmv.cloud
from nextpipe import FlowSpec, app, foreach, join, needs, step

options = nextmv.Options(
    nextmv.Option("input", str, "inputs/", "Path to input dir.", False),
    nextmv.Option("output", str, "outputs/solutions/", "Path to output dir.", False),
    nextmv.Option("assets", str, "outputs/assets/", "Path to asset dir.", False),
)


# >>> Workflow definition
class Flow(FlowSpec):
    @app(app_id="cluster")
    @step
    def cluster():
        """Split the orders using the cluster model."""
        pass

    @needs(predecessors=[cluster])
    @foreach()
    @step
    def transform(result_path: str):
        """Transforms the result for nextroute."""
        # TODO: implement transformation logic here
        pass

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
