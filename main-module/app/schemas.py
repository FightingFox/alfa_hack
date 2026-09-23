from pydantic import BaseModel, Field


class ServiceResult(BaseModel):
    result: list[dict] | None = Field(description="Результат обработки сервиса")
    elapsed: float = Field(description="Время выполнения сервиса в секундах")


class ProcessRequest(BaseModel):
    payload: str | dict[str, ServiceResult] = Field(
        description="Строка для обработки или словарь результатов для демаскирования"
    )
    payload_id: str = Field(description="Идентификатор корреляции")


class ProcessResponse(BaseModel):
    result: str = Field(
        description="Результат обработки (замаскированная строка на прямом шаге, исходная — на обратном)"
    )
