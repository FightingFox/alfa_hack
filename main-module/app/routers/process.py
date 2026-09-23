from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status

from app.masker import mask_text
from app.orchestrator import MaskingProviderError, get_orchestrator
from app.schemas import ProcessRequest, ProcessResponse, Replacement
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
        # Прямой шаг: маскирование через внешние сервисы.
        # Маскирование выполняется только для строки; словарь результатов
        # используется исключительно при демаскировании (existing is not None).
        if not isinstance(request.payload, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="payload должен быть строкой для маскирования",
            )
        try:
            masked = await get_orchestrator().mask(request.payload)
        except MaskingProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        mask_result = mask_text(request.payload, masked)
        replacements = [Replacement(**asdict(r)) for r in mask_result.replacements]
        store.put(
            request.payload_id,
            Record(
                replacements=[asdict(r) for r in mask_result.replacements],
            ),
        )
        return ProcessResponse(
            results=masked,
            masked_text=mask_result.masked_text,
            replacements=replacements,
        )

    # Обратный шаг: демаскирование
    if isinstance(request.payload, str):
        # TODO: замена в request.payload значений из existing.replacements
        restored = request.payload
        for rep in existing.replacements or []:
            restored = restored.replace(rep["mask"], rep["original_text"])
        return ProcessResponse(results=restored)

    # payload_id известен, но payload не является строкой
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="payload должен быть строкой для демаскирования",
    )
