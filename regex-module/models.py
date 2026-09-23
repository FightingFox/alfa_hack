"""Pydantic-модели ответа regex-module.

Формат соответствует остальным сервисам маскирования (gliner_famous, ml_for_all_types):
ProcessResponse содержит поле data со списком найденных сущностей.
"""

from pydantic import BaseModel, Field


class Entity(BaseModel):
    text: str = Field(..., description="Фрагмент текста, где найден тип ПД")
    type: list[str] = Field(..., description="Коды типов ПД")
    score: float = Field(..., description="Уверенность")
    slice: list[int] = Field(..., description="[start, end) позиции в тексте")
    will_be_used: bool = Field(..., description="Будет ли сущность использована")


class ProcessResponse(BaseModel):
    work_time: float = Field(..., description="Время обработки, сек")
    length: int = Field(..., description="Длина входного текста")
    count: int = Field(..., description="Количество найденных сущностей")
    data: list[Entity] = Field(..., description="Найденные сущности")