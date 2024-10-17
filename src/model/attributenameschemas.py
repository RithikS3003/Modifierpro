from pydantic import BaseModel
from typing import List, Optional

class AttributeCreate(BaseModel):
    attribute_name: str
    nounmodifier_id:str
    abbreviation: str
    description: str
    isactive: bool
    # message: Optional[str]
class AttributeUpdate(BaseModel):
    attribute_name: str
    abbreviation: str
    description: str
    isactive: bool

class AttributeData(BaseModel):
    attribute_id: Optional[str]
    nounmodifier_id: str  # Make this field optional
    attribute_name: str
    abbreviation: str
    description: str
    isactive: bool
class AttributeResponse(BaseModel):
    message: str
    data: List[AttributeData]  # Add a message field for responses