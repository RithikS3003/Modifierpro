from pydantic import BaseModel
from typing import List, Optional

class attribute_valueCreate(BaseModel):
    attribute_value: str
    attribute_value_desc: Optional[str] = None
    remarks: Optional[str] = None
    isactive: bool
    nounmodifier_id: str
    attribute_value_abbr: Optional[str] = None  # New field


class Attribute_valueUpdate(BaseModel):
    attribute_value: str
    attribute_value_desc: str
    attribute_value_abbr: str
    remarks:str
    isactive: bool
    nounmodifier_id: Optional[str]

class Attribute_valueData(BaseModel):
    attribute_value_id: Optional[str]
    attribute_value: str  # Make this field optional
    attribute_value_desc: str
    nounmodifier_id: str
    remarks: str
    attribute_value_abbr:str
    isactive: bool
class Attribute_valueResponse(BaseModel):
    message: str
    data: List[Attribute_valueData]