from litestar import Litestar
from litestar.config.cors import CORSConfig

from app.controllers.events import EventsController
from app.controllers.todos import TodosController
from app.controllers.sources import SourcesController

cors_config = CORSConfig(
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app = Litestar(
    route_handlers=[EventsController, TodosController, SourcesController],
    cors_config=cors_config,
)
