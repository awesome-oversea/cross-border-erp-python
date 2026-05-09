from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from erp.shared.bootstrap.data_initializer import DataInitializer
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/data-initializer", tags=["SYS-DataInitializer"])


@router.post("/initialize-all", response_model=None)
async def initialize_all(session: AsyncSession = Depends(get_db_session)):
    initializer = DataInitializer(session)
    results = await initializer.initialize_all()
    await session.commit()
    return Result.ok(data=results, trace_id=trace_id_var.get(""))
