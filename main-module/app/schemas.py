from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    payload: str = Field(description="Строка для обработки")
    payload_id: str = Field(description="Идентификатор корреляции")


class ProcessResponse(BaseModel):
    result: str = Field(description="Результат обработки")
