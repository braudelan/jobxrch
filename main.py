# main.py
import click
import uvicorn


@click.group()
def cli():
    pass


@cli.command()
def pipeline():
    """Crawl LinkedIn saved jobs, fetch JDs, evaluate, and save to DB."""
    from src.pipelines.linkedin import run
    run()


@cli.command()
@click.option("--port", default=8000, help="Port to run the dashboard on.")
def dashboard(port):
    """Start the job evaluation dashboard."""
    uvicorn.run("src.dashboard.app:app", host="127.0.0.1", port=port, reload=True)


if __name__ == "__main__":
    cli()
