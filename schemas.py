from models import Noun
from pydantic import BaseModel
from typing import Optional, List


# Define the request model
class NounCreate(BaseModel):
    abbreviation: str
    description: str
    nounmodifier_id: str


class NounResponse(BaseModel):
    attribute_id: str
    abbreviation: str
    description: str
    nounmodifier_id: str


class NounUpdate(BaseModel):
    abbreviation: Optional[str] = None
    description: Optional[str] = None
    nounmodifier_id: Optional[str] = None


class ModifierData(BaseModel):
    attribute_id: str  # Optional if it could be null
    abbreviation: str
    description: str
    nounmodifier_id: str


class ModifierResponse(BaseModel):
    message: str
    data: List[ModifierData]  # List of ModifierData objects




    # class Config:
    #     orm_mode = True  # Enable ORM mode for compatibility with SQLAlchemy models