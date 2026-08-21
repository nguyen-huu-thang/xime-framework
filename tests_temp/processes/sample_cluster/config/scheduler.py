"""Job khai ở MỌI tiến trình; vòng lặp lịch chỉ chạy ở primary.

Đó là toàn bộ thay đổi của 0.8 với scheduler: nó thành **adapter hạng đơn nhất**,
nên framework chỉ `start()` nó ở primary - và một object không được gọi thì không
chạy. Không cờ nào trong object, không có gì để quên.
"""

from xime.starters.scheduler import IntervalJob, SchedulerConfig, configure_scheduler

from sample_cluster.jobs.tick import TickJob

configure_scheduler(SchedulerConfig(jobs=[IntervalJob(job_class=TickJob, seconds=3600)]))
