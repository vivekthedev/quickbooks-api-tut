from pydantic import BaseModel
from typing import List, Optional


class ItemRef(BaseModel):
    name: str
    value: str


class SalesItemLineDetail(BaseModel):
    ItemRef: ItemRef


class LineItem(BaseModel):
    DetailType: str
    Amount: float
    SalesItemLineDetail: SalesItemLineDetail


class CustomerRef(BaseModel):
    value: str


class InvoiceModel(BaseModel):
    Line: List[LineItem]
    CustomerRef: CustomerRef
