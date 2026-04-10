
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.router.layout_ws import layout_router
from api.router.system_definition_ws import system_definition_router
from api.router.internet_search_ws import internet_search_router
from api.router.overall_observer_ws import overall_observer_router

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
app.include_router(overall_observer_router)