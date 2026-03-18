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


@cli.command("evaluate-all")
@click.option("--force", is_flag=True, default=False, help="Re-evaluate jobs that already have an evaluation.")
def evaluate_all(force):
    """Evaluate all unevaluated jobs (or all jobs with --force)."""
    from src.db.database import init_db, get_unevaluated_jobs, get_jobs_with_latest_evaluation, save_evaluation
    from src.llm_utils.evaluate import evaluate_job

    init_db()

    if force:
        jobs = [j for j in get_jobs_with_latest_evaluation() if j.get("description")]
        click.echo(f"Force mode: evaluating {len(jobs)} jobs.")
    else:
        jobs = [j for j in get_unevaluated_jobs() if j.get("description")]
        click.echo(f"Found {len(jobs)} unevaluated jobs.")

    for i, job in enumerate(jobs, 1):
        click.echo(f"[{i}/{len(jobs)}] {job['job_title']} @ {job['company']} ... ", nl=False)
        try:
            result, chash = evaluate_job(job)
            save_evaluation(job["id"], chash, result)
            click.echo(f"score={result.score}")
        except Exception as e:
            click.echo(f"ERROR: {e}")

    click.echo("Done.")


@cli.command()
@click.option("--port", default=8000, help="Port to run the dashboard on.")
def dashboard(port):
    """Start the job evaluation dashboard."""
    uvicorn.run("src.dashboard.app:app", host="127.0.0.1", port=port, reload=True,
                reload_includes=["*.html", "*.css", "*.js"])


if __name__ == "__main__":
    cli()
