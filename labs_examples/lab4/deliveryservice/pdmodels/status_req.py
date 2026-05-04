from enum import Enum

from pydantic import BaseModel

STATUS_DELIVERED = "Delivered"
STATUS_CREATED = "Created"
STATUS_CANCELED = "Canceled"
STATUS_DELIVERING = "Delivering"


class StatusEnum(str, Enum):
    delivered = STATUS_DELIVERED
    created = STATUS_CREATED
    canceled = STATUS_CANCELED
    delivering = STATUS_DELIVERING


class StatusModel(BaseModel):
    status: StatusEnum = StatusEnum.created
