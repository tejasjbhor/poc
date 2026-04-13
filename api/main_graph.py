
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.layout_ws import layout_router
from api.requirement_generation_ws import requirement_generation_router
from api.system_definition_ws import system_definition_router
from api.internet_search_ws import internet_search_router
from api.overall_observer_ws import overall_observer_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(layout_router)
app.include_router(system_definition_router)
app.include_router(internet_search_router)
app.include_router(requirement_generation_router)
app.include_router(overall_observer_router)