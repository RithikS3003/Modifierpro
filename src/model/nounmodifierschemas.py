from pydantic import BaseModel
from typing import List, Optional

class NounModifierCreate(BaseModel):
    # noun_id: str
    # modifier_id: str
    noun: str
    modifier:str
    abbreviation: str
    description: str
    isactive: bool
    # noun_modifier_id: str
    # message: Optional[str]
class NounModifierUpdate(BaseModel):
    # noun_id: str
    # modifier_id: str
    noun: str
    modifier:str
    abbreviation: str
    description: str
    isactive: bool

class NounModifierData(BaseModel):
    noun_id: str
    modifier_id: str
    noun: str
    modifier: str
    abbreviation: str
    description: str
    isactive: bool
    nounmodifier_id: str
    noun_modifier:str
class NounModifierResponse(BaseModel):
    message: str
    data:List[NounModifierData]# Add a message field for responses