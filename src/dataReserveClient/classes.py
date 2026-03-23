from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class SeriesStorage(BaseModel):
    SeriesId: UUID
    StorageId: UUID
    DatabaseName: str
    TableName: str

class DataItem(BaseModel):
    SeriesId: UUID
    Timestamp: datetime
    Value: float
