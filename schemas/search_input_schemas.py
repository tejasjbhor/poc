from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(description="Search query")