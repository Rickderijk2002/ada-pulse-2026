from pydantic import BaseModel


class DeliveryReq(BaseModel):
    id: int
    customer_id: str
    provider_id: str
    package_id: str
    delivery_time: str
