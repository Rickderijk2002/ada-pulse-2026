from datetime import datetime

from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from daos.delivery_dao import DeliveryDAO
from daos.status_dao import StatusDAO
from db import Session
from pdmodels.delivery_req import DeliveryReq
from pdmodels.status_req import STATUS_CREATED


class Delivery:
    @staticmethod
    def create(d_req: DeliveryReq):
        session = Session()
        delivery = DeliveryDAO(d_req.id, d_req.customer_id, d_req.provider_id, d_req.package_id, datetime.now(),
                               datetime.strptime(d_req.delivery_time, '%Y-%m-%d %H:%M:%S.%f'),
                               StatusDAO(d_req.id, STATUS_CREATED, datetime.now()))
        session.add(delivery)
        session.commit()
        session.refresh(delivery)
        session.close()
        return JSONResponse(content=jsonable_encoder({'delivery_id': delivery.id}), status_code=status.HTTP_201_CREATED)

    @staticmethod
    def get(d_id):
        session = Session()
        # https://docs.sqlalchemy.org/en/14/orm/query.html
        # https://www.tutorialspoint.com/sqlalchemy/sqlalchemy_orm_using_query.htm
        delivery = session.query(DeliveryDAO).filter(DeliveryDAO.id == d_id).first()

        if delivery:
            status_obj = delivery.status
            text_out = {
                "customer_id:": delivery.customer_id,
                "provider_id": delivery.provider_id,
                "package_id": delivery.package_id,
                "order_time": delivery.order_time.isoformat(),
                "delivery_time": delivery.delivery_time.isoformat(),
                "status": {
                    "status": status_obj.status_name,
                    "last_update": status_obj.last_update.isoformat(),
                }
            }
            session.close()
            return JSONResponse(content=jsonable_encoder(text_out),
                                status_code=status.HTTP_200_OK)
        else:
            session.close()
            return JSONResponse(content=jsonable_encoder({'message': f'There is no delivery with id {d_id}'}),
                                status_code=status.HTTP_404_NOT_FOUND)

    @staticmethod
    def delete(d_id):
        session = Session()
        delivery = session.query(DeliveryDAO).filter(DeliveryDAO.id == d_id).first()

        if delivery:
            session.delete(delivery.status)
            session.delete(delivery)
            session.commit()
            session.close()
            return JSONResponse(content=jsonable_encoder({'message': 'The delivery was removed'}),
                                status_code=status.HTTP_200_OK)
        else:
            session.close()
            return JSONResponse(content=jsonable_encoder({'message': f'There is no delivery with id {d_id}'}),
                                status_code=status.HTTP_404_NOT_FOUND)
