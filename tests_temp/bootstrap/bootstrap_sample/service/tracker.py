class TrackerService:
    """
    Records PostConstruct / PreDestroy calls.
    Used by bootstrap tests to verify lifecycle orchestration.
    """

    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def post_construct(self) -> None:
        self.started = True

    async def pre_destroy(self) -> None:
        self.stopped = True


class GreeterService:
    """Depends on TrackerService - used to verify dependency ordering."""

    def __init__(self, tracker: TrackerService) -> None:
        self.tracker = tracker
        self.started = False

    async def post_construct(self) -> None:
        self.started = True
