from pydantic import BaseModel
from datetime import datetime
from uuid import UUID



class DataItem(BaseModel):
    SeriesId: UUID
    Timestamp: datetime
    Value: float
