"""
Test ScheduledJob Protocol:
  - Class có async def run() → thoả Protocol
  - Class không có run() → không thoả Protocol
  - Class chỉ có các method khác → không thoả Protocol
  - Sync def run() cũng thoả isinstance (structural check, không kiểm tra async)
  - Protocol là runtime_checkable → isinstance dùng được
"""
from xime.starters.scheduler._job import ScheduledJob


class TestScheduledJobProtocol:
    def test_class_with_async_run_satisfies_protocol(self):
        class ValidJob:
            async def run(self) -> None:
                pass

        assert isinstance(ValidJob(), ScheduledJob)

    def test_class_without_any_method_fails(self):
        class EmptyJob:
            pass

        assert not isinstance(EmptyJob(), ScheduledJob)

    def test_class_with_other_async_method_but_no_run_fails(self):
        class WrongMethodJob:
            async def execute(self) -> None:
                pass

        assert not isinstance(WrongMethodJob(), ScheduledJob)

    def test_sync_run_also_satisfies_structural_check(self):
        # isinstance chỉ kiểm tra sự tồn tại của attribute, không kiểm tra async/sync.
        # Trường hợp này được bắt ở runtime khi APScheduler gọi run() và xử lý kết quả.
        class SyncJob:
            def run(self) -> None:
                pass

        assert isinstance(SyncJob(), ScheduledJob)

    def test_two_independent_valid_job_classes_both_satisfy(self):
        class JobA:
            async def run(self) -> None:
                pass

        class JobB:
            async def run(self) -> None:
                pass

        assert isinstance(JobA(), ScheduledJob)
        assert isinstance(JobB(), ScheduledJob)

    def test_run_as_non_callable_attribute_still_satisfies_structural_check(self):
        # Python's runtime_checkable Protocol chỉ kiểm tra PRESENCE của attribute,
        # không kiểm tra callable hay signature. Đây là limitation đã biết của
        # structural typing — lỗi thực sự sẽ được phát hiện khi APScheduler gọi run().
        class WeirdJob:
            run = "not_a_method"

        assert isinstance(WeirdJob(), ScheduledJob)
