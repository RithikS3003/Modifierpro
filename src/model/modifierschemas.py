from pydantic import BaseModel
from typing import List, Optional

class ModifierCreate(BaseModel):
    modifier: str
    abbreviation: str
    description: str
    isactive: bool
    message: Optional[str]

class ModifierUpdate(BaseModel):
    modifier: str
    abbreviation: str
    description: str
    isactive: bool
    # message: Optional[str]

class ModifierData(BaseModel):
    modifier_id: Optional[str]  # Make this field optional
    modifier: str
    abbreviation: str
    description: str
    isactive: bool

class ModifierResponse(BaseModel):
    message: str
    data: List[ModifierData]