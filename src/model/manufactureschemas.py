from pydantic import BaseModel
from typing import List, Optional

class ManufacturerCreate(BaseModel):
    manufacturid: str
    manufacturname: str
    manufacturdesc: str
    remarks: str
    isactive: bool
    # manufacturer_abbr: str  # Adjust based on your database type

class ManufacturerUpdate(BaseModel):
    manufacturname: str
    manufacturdesc: Optional[str] = None
    remarks: Optional[str] = None
    isactive: bool
    nounmodifier_id: str

class ManufacturerData(BaseModel):
    manufacturid: str
    manufacturname: str
    manufacturdesc: str
    remarks: Optional[str]
    isactive: bool
    nounmodifier_id: str
    # manufacturer_abbr:str

class ManufacturerResponse(BaseModel):
    message: str
    data: List[ManufacturerData]