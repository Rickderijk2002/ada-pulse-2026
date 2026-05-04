import datetime

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from daos.delivery_dao import DeliveryDAO
from db import Session


class Status:
    @staticmethod
    def update(d_id, status_text):
        session = Session()
        delivery = session.query(DeliveryDAO).filter(DeliveryDAO.id == int(d_id)).first()
        delivery.status.status_name = status_text
        delivery.status.last_update = datetime.datetime.now()
        session.commit()
        session.close()
        return JSONResponse(content=jsonable_encoder({'message': 'The delivery status was updated'}),
                            status_code=200)
