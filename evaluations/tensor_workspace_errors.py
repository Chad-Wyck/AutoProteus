"""Typed stops at the trusted host/guest boundary; no workload on import."""

class InfrastructureStop(BaseException):
    pass


class GlobalDeadlineStop(InfrastructureStop):
    pass


class CellAllowanceExceeded(Exception):
    pass
