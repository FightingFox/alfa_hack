from pydantic import BaseModel, Field


class Entity(BaseModel):
    text: str = Field(description="Фрагмент текста, где найден тип ПД")
    type: list[str] = Field(description="Коды типов ПД")
    score: float = Field(description="Уверенность модели")
    slice: list[int] = Field(description="[start, end) позиции в тексте")
    will_be_used: bool = Field(description="Будет ли сущность использована")


class ServiceResult(BaseModel):
    result: list[Entity] | None = Field(description="Результат обработки сервиса")
    elapsed: float = Field(description="Время выполнения сервиса в секундах")


class ProcessRequest(BaseModel):
    payload: str | dict[str, ServiceResult] = Field(
        description="Строка для обработки или словарь результатов для демаскирования"
    )
    payload_id: str = Field(description="Идентификатор корреляции")


class Replacement(BaseModel):
    slice: list[int] = Field(description="[start, end) позиции в исходном тексте")
    types: list[str] = Field(description="Типы ПД представителя кластера")
    mask: str = Field(description="Маска вида {{ TYPE1,TYPE2 N }}")
    original_text: str = Field(description="Исходный фрагмент text[start:end]")


class ProcessResponse(BaseModel):
    results: dict[str, ServiceResult] | str = Field(
        description="Результаты обработки по каждому сервису или исходная строка при демаскировании"
    )
    masked_text: str | None = Field(
        default=None,
        description="Замаскированный текст (только при маскировании)",
    )
    replacements: list[Replacement] | None = Field(
        default=None,
        description="Список замен (только при маскировании)",
    )
