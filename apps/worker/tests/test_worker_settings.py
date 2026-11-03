from nfactory_core.config import Settings
from nfactory_worker.main import build_worker_settings, ping


def test_worker_reads_redis_url_from_settings() -> None:
    settings = build_worker_settings(Settings(redis_url="redis://cache.internal:6380/2"))

    redis = settings["redis_settings"]
    assert (redis.host, redis.port, redis.database) == ("cache.internal", 6380, 2)


def test_worker_concurrency_follows_max_concurrent_runs() -> None:
    settings = build_worker_settings(Settings(max_concurrent_runs=3))
    assert settings["max_jobs"] == 3


async def test_ping_job_answers() -> None:
    assert await ping({}) == "pong"


def test_factory_job_and_lifecycle_hooks_are_registered() -> None:
    settings = build_worker_settings(Settings())
    names = {getattr(f, "__name__", "") for f in settings["functions"]}
    assert {"ping", "run_factory"} <= names
    assert settings["on_startup"] is not None and settings["on_shutdown"] is not None


def test_orphaned_runs_are_recovered_every_minute() -> None:
    settings = build_worker_settings(Settings())
    names = {job.name for job in settings["cron_jobs"]}
    assert "cron:recover_runs" in names


def test_finished_jobs_keep_no_result_so_an_approved_run_can_be_queued_again() -> None:
    # The job id is the run id; a kept result would make ARQ drop the re-enqueue.
    assert build_worker_settings(Settings())["keep_result"] == 0


def test_runner_is_the_sandbox_when_configured(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from nfactory_worker.main import make_runner
    from nfactory_worker.runner import LocalRunner, SandboxRunner

    sandboxed = Settings(
        nfactory_sandbox_url="http://sandbox:8800", nfactory_sandbox_token="x" * 20
    )
    assert isinstance(make_runner(sandboxed), SandboxRunner)
    assert isinstance(make_runner(Settings(workspace_root=str(tmp_path))), LocalRunner)


def test_checkpointer_url_uses_the_plain_libpq_scheme() -> None:
    from nfactory_worker.main import checkpoint_url

    url = checkpoint_url(Settings(database_url="postgresql+psycopg://u:p@h:5432/db"))
    assert url == "postgresql://u:p@h:5432/db"


def test_knowledge_indexing_job_is_registered_and_caught_up_every_minute() -> None:
    from nfactory_core.pipeline import INDEX_JOB

    settings = build_worker_settings(Settings())
    names = {getattr(f, "__name__", "") for f in settings["functions"]}
    assert INDEX_JOB in names
    assert "cron:index_pending" in {job.name for job in settings["cron_jobs"]}
