from fastapi.responses import JSONResponse
from typing import Any, Dict

class ResponseHandler:
    @staticmethod
    def success(data: Dict[str, Any], status_code: int = 200) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content=data
        )