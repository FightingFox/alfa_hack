from fastapi import APIRouter, HTTPException, status

from app.orchestrator import MaskingProviderError, get_orchestrator
from app.schemas import ProcessRequest, ProcessResponse
from app.store import Record, get_store

router = APIRouter(tags=["process"])


@router.post(
    "/process",
    response_model=ProcessResponse,
    responses={
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Слишком много запросов"},
    },
)
async def process(request: ProcessRequest) -> ProcessResponse:
    """Маскирование/демаскирование строки, коррелируется по payload_id."""
    store = get_store()
    existing = store.get(request.payload_id)

    if existing is None:
        # Прямой шаг: маскирование через внешние сервисы
        try:
            masked = await get_orchestrator().mask(request.payload)
        except MaskingProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        store.put(request.payload_id, Record(original=request.payload, masked=masked))
        return ProcessResponse(results=masked)

    # Обратный шаг: демаскирование
    payload = (
        {k: v.model_dump() for k, v in request.payload.items()}
        if isinstance(request.payload, dict)
        else request.payload
    )
    if payload == existing.masked:
        return ProcessResponse(results=existing.original)

    # payload_id известен, но payload не совпадает с ранее возвращённой маской
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="payload не соответствует ранее замаскированной строке для данного payload_id",
    )
