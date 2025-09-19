# File: schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

from pydantic import BaseModel, Field
from typing import List, Optional

class Place(BaseModel):
    name: str
    url: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_url: Optional[float] = None
    description: Optional[float] = None



class PlacesResponse(BaseModel):
    destination: str
    source: str = Field(description="'cache' or 'live'")
    count: int
    data: List[Place]
    cache_file: Optional[str] = None
    note: Optional[str] = None
