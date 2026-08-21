"""
Test CronJob, IntervalJob, SchedulerConfig, scheduler_registry, configure_scheduler:

  CronJob:
    - lưu đúng job_class và cron
    - id mặc định là None
    - lưu id tuỳ chỉnh

  IntervalJob:
    - lưu đúng job_class
    - hours / minutes / seconds mặc định là 0
    - lưu đúng các giá trị interval
    - id mặc định là None, lưu id tuỳ chỉnh

  SchedulerConfig:
    - jobs mặc định là list rỗng
    - timezone mặc định là "UTC"
    - lưu đúng jobs và timezone tuỳ chỉnh
    - jobs list độc lập giữa các instance (mutable default không chia sẻ)
    - chấp nhận kết hợp CronJob và IntervalJob

  scheduler_registry + configure_scheduler:
    - get() trả về None trước khi configure
    - configure_scheduler() lưu config vào registry
    - configure_scheduler() không clone - trả về đúng object
    - configure_scheduler() gọi lần 2 ghi đè config cũ
    - config được lưu bảo toàn jobs và timezone
"""
import pytest

from xime.starters.scheduler._config import (
    CronJob,
    IntervalJob,
    SchedulerConfig,
    configure_scheduler,
    scheduler_registry,
)


class _JobA:
    pass


class _JobB:
    pass


# ---------------------------------------------------------------------------
# CronJob
# ---------------------------------------------------------------------------

class TestCronJob:
    def test_stores_job_class(self):
        job = CronJob(job_class=_JobA, cron="0 0 * * *")
        assert job.job_class is _JobA

    def test_stores_cron_expression(self):
        job = CronJob(job_class=_JobA, cron="0 9 * * 1-5")
        assert job.cron == "0 9 * * 1-5"

    def test_id_defaults_to_none(self):
        job = CronJob(job_class=_JobA, cron="0 0 * * *")
        assert job.id is None

    def test_stores_custom_id(self):
        job = CronJob(job_class=_JobA, cron="0 0 * * *", id="daily-report")
        assert job.id == "daily-report"


# ---------------------------------------------------------------------------
# IntervalJob
# ---------------------------------------------------------------------------

class TestIntervalJob:
    def test_stores_job_class(self):
        job = IntervalJob(job_class=_JobA, seconds=60)
        assert job.job_class is _JobA

    def test_hours_default_to_zero(self):
        job = IntervalJob(job_class=_JobA, minutes=5)
        assert job.hours == 0

    def test_minutes_default_to_zero(self):
        job = IntervalJob(job_class=_JobA, seconds=30)
        assert job.minutes == 0

    def test_seconds_default_to_zero(self):
        job = IntervalJob(job_class=_JobA, minutes=10)
        assert job.seconds == 0

    def test_id_defaults_to_none(self):
        job = IntervalJob(job_class=_JobA, seconds=60)
        assert job.id is None

    def test_stores_all_interval_fields(self):
        job = IntervalJob(job_class=_JobA, hours=1, minutes=30, seconds=15)
        assert job.hours == 1
        assert job.minutes == 30
        assert job.seconds == 15

    def test_stores_custom_id(self):
        job = IntervalJob(job_class=_JobA, seconds=60, id="cleanup-job")
        assert job.id == "cleanup-job"


# ---------------------------------------------------------------------------
# SchedulerConfig
# ---------------------------------------------------------------------------

class TestSchedulerConfig:
    def test_jobs_default_to_empty_list(self):
        config = SchedulerConfig()
        assert config.jobs == []

    def test_timezone_defaults_to_utc(self):
        config = SchedulerConfig()
        assert config.timezone == "UTC"

    def test_stores_jobs_list(self):
        jobs = [CronJob(job_class=_JobA, cron="0 0 * * *")]
        config = SchedulerConfig(jobs=jobs)
        assert config.jobs is jobs

    def test_stores_custom_timezone(self):
        config = SchedulerConfig(timezone="Asia/Ho_Chi_Minh")
        assert config.timezone == "Asia/Ho_Chi_Minh"

    def test_jobs_lists_are_independent_between_instances(self):
        """field(default_factory=list) → mỗi instance có list riêng."""
        config_a = SchedulerConfig()
        config_b = SchedulerConfig()
        config_a.jobs.append(CronJob(job_class=_JobA, cron="0 0 * * *"))
        assert config_b.jobs == []

    def test_accepts_mixed_cron_and_interval_jobs(self):
        config = SchedulerConfig(jobs=[
            CronJob(job_class=_JobA, cron="0 0 * * *"),
            IntervalJob(job_class=_JobB, minutes=30),
        ])
        assert len(config.jobs) == 2
        assert isinstance(config.jobs[0], CronJob)
        assert isinstance(config.jobs[1], IntervalJob)


# ---------------------------------------------------------------------------
# scheduler_registry + configure_scheduler
# ---------------------------------------------------------------------------

class TestSchedulerRegistry:
    def test_returns_none_before_configure(self):
        scheduler_registry._config = None
        assert scheduler_registry.get() is None

    def test_configure_scheduler_stores_config(self):
        config = SchedulerConfig()
        configure_scheduler(config)
        assert scheduler_registry.get() is not None

    def test_configure_scheduler_stores_exact_object_not_clone(self):
        config = SchedulerConfig()
        configure_scheduler(config)
        assert scheduler_registry.get() is config

    def test_configure_scheduler_twice_overwrites_previous(self):
        configure_scheduler(SchedulerConfig(timezone="UTC"))
        configure_scheduler(SchedulerConfig(timezone="Asia/Ho_Chi_Minh"))
        assert scheduler_registry.get().timezone == "Asia/Ho_Chi_Minh"

    def test_configure_scheduler_preserves_jobs(self):
        jobs = [
            CronJob(job_class=_JobA, cron="0 0 * * *"),
            IntervalJob(job_class=_JobB, minutes=15),
        ]
        configure_scheduler(SchedulerConfig(jobs=jobs))
        assert scheduler_registry.get().jobs == jobs

    def test_configure_scheduler_preserves_timezone(self):
        configure_scheduler(SchedulerConfig(timezone="Europe/Paris"))
        assert scheduler_registry.get().timezone == "Europe/Paris"
