from typing import Annotated

from pydantic import Field

# shared validated field types: the same rules for LLM tools, MCP tools and A2A skills
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="identifier, e.g. a1")]
UserId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="user id (uuid)")]
SearchQuery = Annotated[str, Field(min_length=0, max_length=60, description="part of title, artist or genre")]
TracksPlayed = Annotated[int, Field(ge=0, le=100, description="how many tracks are played")]
Rating = Annotated[int, Field(ge=1, le=10, description="rating from 1 to 10")]
