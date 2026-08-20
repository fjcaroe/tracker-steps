import enum


class TrackingStatus(str, enum.Enum):
    open = "open"
    closed = "closed"
