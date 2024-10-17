from pydantic import BaseModel
from typing import List, Optional

class NounCreate(BaseModel):
    noun: str
    abbreviation: str
    description: str
    isactive: bool

class NounUpdate(BaseModel):
    noun: str
    abbreviation: str
    description: str
    isactive: bool

class NounData(BaseModel):
    noun_id: str
    noun: str
    abbreviation: str
    description: str
    isactive: bool

class NounResponse(BaseModel):
    message: str
    data: List[NounData]