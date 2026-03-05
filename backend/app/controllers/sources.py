from litestar import Controller, get, post, put, delete
from litestar.exceptions import NotFoundException

from app.models.dtos import Source, SourceCreate, SourceUpdate
from app.db.sources_store import SourcesStore


def get_sources_store() -> SourcesStore:
    return SourcesStore()


class SourcesController(Controller):
    path = "/api/sources"

    @get()
    async def list_sources(self) -> list[Source]:
        store = get_sources_store()
        return store.list_sources()

    @get("/{source_id:str}")
    async def get_source(self, source_id: str) -> Source:
        store = get_sources_store()
        s = store.get_source(source_id)
        if not s:
            raise NotFoundException(detail="Source not found")
        return s

    @post()
    async def create_source(self, data: SourceCreate) -> Source:
        store = get_sources_store()
        return store.add_source(data)

    @put("/{source_id:str}")
    async def update_source(self, source_id: str, data: SourceUpdate) -> Source:
        store = get_sources_store()
        s = store.update_source(source_id, data)
        if not s:
            raise NotFoundException(detail="Source not found")
        return s

    @delete("/{source_id:str}")
    async def delete_source(self, source_id: str) -> None:
        store = get_sources_store()
        if not store.delete_source(source_id):
            raise NotFoundException(detail="Source not found")
