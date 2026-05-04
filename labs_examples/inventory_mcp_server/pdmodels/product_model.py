from pydantic import BaseModel, Field


class ProductModel(BaseModel):
    type: str = Field(description="Product type")
    quantity: int = Field(description="Product Quantity or inventor level of a product")
