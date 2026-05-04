import uvicorn
from fastapi import FastAPI

from db import Base, engine
from pdmodels.delivery_req import DeliveryReq
from pdmodels.status_req import StatusModel
from resources.delivery import Delivery
from resources.status import Status

app = FastAPI()
Base.metadata.create_all(engine)


@app.post("/deliveries")
def create_delivery(d_req: DeliveryReq):
    return Delivery.create(d_req)


@app.get('/deliveries/{d_id}')
def get_delivery(d_id: int):
    return Delivery.get(d_id)


@app.put('/deliveries/{d_id}/status')
def update_delivery_status(d_id: int, new_status: StatusModel):
    return Status.update(d_id, new_status.status)


@app.delete('/deliveries/{d_id}')
def delete_delivery(d_id: int):
    return Delivery.delete(d_id)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
