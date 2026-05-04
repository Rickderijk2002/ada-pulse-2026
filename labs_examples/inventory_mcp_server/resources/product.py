from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from pdmodels.product_model import ProductModel

inventories = [
    {
        "type": "Laptop",
        "quantity": 1000
    },
    {
        "type": "Phone",
        "quantity": 5000
    }
]


class Product:
    def read(self, type):
        for record in inventories:
            if type == record["type"]:
                return JSONResponse(content=jsonable_encoder(record),
                                    status_code=status.HTTP_200_OK)
        return JSONResponse(content=jsonable_encoder({'message': "There is no product type " + type}),
                            status_code=status.HTTP_404_NOT_FOUND)

    def update(self, type, value):
        for record in inventories:
            if type == record["type"]:
                record["quantity"] = record["quantity"] - value
                return JSONResponse(content=jsonable_encoder(record),
                                    status_code=status.HTTP_200_OK)
        return JSONResponse(content=jsonable_encoder({'message': "There is no product type " + type}),
                            status_code=status.HTTP_404_NOT_FOUND)


class Products:
    def create(self, p_model:ProductModel):
        record_to_be_created = p_model.model_dump(mode="json")
        type = p_model.type
        for record in inventories:
            if type == record["type"]:
                return JSONResponse(content=jsonable_encoder({'message': "There is no product type " + type}),
                                    status_code=status.HTTP_404_NOT_FOUND)
        inventories.append(record_to_be_created)
        return JSONResponse(content=jsonable_encoder(record_to_be_created),
                            status_code=status.HTTP_201_CREATED)
