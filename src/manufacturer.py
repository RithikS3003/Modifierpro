# src/manufacturer.py
# from django.db import app
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import List, Optional
import io
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

app = FastAPI()

# Add CORS middleware to allow requests from all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection details
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@192.168.0.190:5432/tagminds"

# Create the async engine and session
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)


# Dependency to get the DB session
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

TABLE_NAME = "manufacturer_master"
# Pydantic models
class ManufacturerCreate(BaseModel):
    manufacturname: str
    manufacturdesc: Optional[str] = None
    remarks: Optional[str] = None
    isactive: bool
    nounmodifier_id: str  # Adjust based on your database type

class ManufacturerResponse(BaseModel):
    manufacturid: str
    manufacturname: str
    manufacturdesc: str
    remarks: str
    isactive: bool
    nounmodifier_id: str  # Add this field
    message: str

async def generate_manufacturid(db: AsyncSession) -> str:
    # Fetch the maximum existing manufacturid
    query = text("SELECT MAX(manufacturid) FROM manufacturer_master")
    result = await db.execute(query)
    last_id = result.scalar()

    if last_id:
        # Extract the numeric part and increment it
        try:
            prefix, num_part = last_id.split('_')
            new_id_number = int(num_part) + 1
            return f"{prefix}_{new_id_number:04d}"  # Pad with leading zeros
        except ValueError:
            raise HTTPException(status_code=500, detail=f"Invalid manufacturid format: {last_id}")
    else:
        return "MFR_0001"  # Start with this if no entries exist

@app.post("/manufacturer", response_model=ManufacturerResponse)
async def create_manufacturer(entry: ManufacturerCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Generate new manufacturid
        new_manufacturid = await generate_manufacturid(db)

        # Validate that manufacturname is not empty or just whitespace
        if not entry.manufacturname.strip():
            raise HTTPException(status_code=400, detail="Manufacturer name cannot be an empty string or just whitespace")

        # Check if the manufacturer already exists (optional check to prevent duplicates by manufacturer name)
        existing_manufacturer = await db.execute(text(f"SELECT 1 FROM manufacturer_master WHERE manufacturname = :manufacturname"), {"manufacturname": entry.manufacturname})
        if existing_manufacturer.fetchone():
            raise HTTPException(status_code=400, detail="Manufacturer already exists.")

        # Insert into the database
        query = text(f"""
            INSERT INTO manufacturer_master (manufacturid, manufacturname, manufacturdesc, remarks, isactive, nounmodifier_id)
            VALUES (:manufacturid, :manufacturname, :manufacturdesc, :remarks, :isactive, :nounmodifier_id)
            RETURNING manufacturid, manufacturname, manufacturdesc, remarks, isactive, nounmodifier_id
        """)
        result = await db.execute(query, {
            "manufacturid": new_manufacturid,
            "manufacturname": entry.manufacturname,
            "manufacturdesc": entry.manufacturdesc,
            "remarks": entry.remarks,
            "isactive": entry.isactive,
            "nounmodifier_id": entry.nounmodifier_id,
        })
        await db.commit()

        # Fetching the inserted values
        manufacturid, manufacturname, manufacturdesc, remarks, isactive, nounmodifier_id = result.fetchone()

        return ManufacturerResponse(
            manufacturid=manufacturid,
            manufacturname=manufacturname,
            manufacturdesc=manufacturdesc,
            remarks=remarks,
            isactive=isactive,
            nounmodifier_id=nounmodifier_id,
            message="Manufacturer created successfully"
        )

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Integrity Error: Duplicate manufacturer entry.")
    except SQLAlchemyError as sql_err:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(sql_err)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

 
@app.get("/manufacturers", response_model=List[ManufacturerResponse])
async def get_manufacturers(db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"SELECT manufacturid, manufacturname, manufacturdesc, remarks, isactive, nounmodifier_id FROM manufacturer_master")
        result = await db.execute(query)
        rows = result.fetchall()

        return [
            ManufacturerResponse(
                manufacturid=row.manufacturid,
                manufacturname=row.manufacturname,
                manufacturdesc=row.manufacturdesc,
                remarks=row.remarks,
                isactive=row.isactive,
                nounmodifier_id=row.nounmodifier_id,
                message="ok"
            ) for row in rows
        ]
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/{manufacturid}", response_model=ManufacturerResponse)
async def update_manufacturer(manufacturid: int, manufacturer: ManufacturerCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"""
            UPDATE {TABLE_NAME}
            SET manufacturname = :manufacturname,
                manufacturdesc = :manufacturdesc,
                remarks = :remarks,
                isactive = :isactive,
                nounmodifier_id = :nounmodifier_id
            WHERE manufacturid = :manufacturid
            RETURNING manufacturid, manufacturname, manufacturdesc, remarks, isactive
        """)
        result = await db.execute(query, {
            "manufacturid": manufacturid,
            "manufacturname": manufacturer.manufacturname,
            "manufacturdesc": manufacturer.manufacturdesc,
            "remarks": manufacturer.remarks,
            "isactive": manufacturer.isactive,
            "nounmodifier_id": manufacturer.nounmodifier_id
        })
        await db.commit()

        updated_row = result.fetchone()
        if not updated_row:
            raise HTTPException(status_code=404, detail="Manufacturer not found")

        return ManufacturerResponse(**updated_row._asdict(), message="Manufacturer updated successfully")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/{manufacturid}", response_model=dict)
async def delete_manufacturer(manufacturid: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"DELETE FROM {TABLE_NAME} WHERE manufacturid = :manufacturid")
        result = await db.execute(query, {"manufacturid": manufacturid})  # Ensure manufacturid is passed as a string
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Manufacturer not found")

        return {"message": "Manufacturer deleted successfully"}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
