from pydantic import BaseModel


class AddIn(BaseModel):
    session_id: str
    product_id: str
    quantity: int = 1


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


class SessionIn(BaseModel):
    session_id: str


class CreateOrderIn(BaseModel):
    session_id: str
    product_ids: list[str] = []
    order_ids: list[str] = []
    separate: bool = False


class CaptureIn(BaseModel):
    session_id: str
    order_id: str
