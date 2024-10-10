# src/attribute_value.py
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

TABLE_NAME = "attribute_value_master"
# Pydantic models
class attribute_valueCreate(BaseModel):
    attribute_value: str
    attribute_value_desc: Optional[str] = None
    remarks: Optional[str] = None
    isactive: bool
    nounmodifier_id: str
    attribute_value_abbr: Optional[str] = None  # New field

class attribute_valueResponse(BaseModel):
    attribute_value_id: str
    attribute_value: str
    attribute_value_desc: str
    remarks: str
    isactive: bool
    nounmodifier_id: str
    attribute_value_abbr: Optional[str]  # New field
    message: str

async def generate_attribute_value_id(db: AsyncSession) -> str:
    # Fetch the maximum existing attribute_value_id
    query = text("SELECT MAX(attribute_value_id) FROM attribute_value_master")
    result = await db.execute(query)
    last_id = result.scalar()

    if last_id:
        # Extract the numeric part and increment it
        try:
            prefix, num_part = last_id.split('_')
            new_id_number = int(num_part) + 1
            return f"{prefix}_{new_id_number:04d}"  # Pad with leading zeros
        except ValueError:
            raise HTTPException(status_code=500, detail=f"Invalid attribute_value_id format: {last_id}")
    else:
        return "ATRV_0001"  # Start with this if no entries exist

@app.post("/attribute_value", response_model=attribute_valueResponse)
async def create_attribute_value(entry: attribute_valueCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Generate new attribute_value_id
        new_attribute_value_id = await generate_attribute_value_id(db)

        # Validate that attribute_value is not empty or just whitespace
        if not entry.attribute_value.strip():
            raise HTTPException(status_code=400, detail="attribute_value name cannot be an empty string or just whitespace")

        # Check if the attribute_value already exists (optional check to prevent duplicates by attribute_value name)
        existing_attribute_value = await db.execute(text(f"SELECT 1 FROM attribute_value_master WHERE attribute_value = :attribute_value"), {"attribute_value": entry.attribute_value})
        if existing_attribute_value.fetchone():
            raise HTTPException(status_code=400, detail="attribute_value already exists.")

        # Insert into the database
        query = text(f"""
            INSERT INTO attribute_value_master (attribute_value_id, attribute_value, attribute_value_desc, remarks, isactive, nounmodifier_id,attribute_value_abbr)
            VALUES (:attribute_value_id, :attribute_value, :attribute_value_desc, :remarks, :isactive, :nounmodifier_id, :attribute_value_abbr)
            RETURNING attribute_value_id, attribute_value, attribute_value_desc, remarks, isactive, nounmodifier_id, attribute_value_abbr
        """)
        result = await db.execute(query, {
            "attribute_value_id": new_attribute_value_id,
            "attribute_value": entry.attribute_value,
            "attribute_value_desc": entry.attribute_value_desc,
            "remarks": entry.remarks,
            "isactive": entry.isactive,
            "nounmodifier_id": entry.nounmodifier_id,
            "attribute_value_abbr": entry.attribute_value_abbr,
        })
        await db.commit()

        # Fetching the inserted values
        attribute_value_id, attribute_value, attribute_value_desc, remarks, isactive, nounmodifier_id, attribute_value_abbr = result.fetchone()

        return attribute_valueResponse(
            attribute_value_id=attribute_value_id,
            attribute_value=attribute_value,
            attribute_value_desc=attribute_value_desc,
            attribute_value_abbr=attribute_value_abbr,
            remarks=remarks,
            isactive=isactive,
            nounmodifier_id=nounmodifier_id,
            message="attribute_value created successfully"
        )

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Integrity Error: Duplicate attribute_value entry.")
    except SQLAlchemyError as sql_err:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(sql_err)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

 
@app.get("/attribute_values", response_model=List[attribute_valueResponse])
async def get_attribute_values(db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"SELECT attribute_value_id, attribute_value, attribute_value_desc, remarks, isactive, nounmodifier_id, attribute_value_abbr FROM attribute_value_master")
        result = await db.execute(query)
        rows = result.fetchall()

        return [
            attribute_valueResponse(
                attribute_value_id=row.attribute_value_id,
                attribute_value=row.attribute_value,
                attribute_value_desc=row.attribute_value_desc,
                attribute_value_abbr=row.attribute_value_abbr,
                remarks=row.remarks,
                isactive=row.isactive,
                nounmodifier_id=row.nounmodifier_id,
                message="ok"
            ) for row in rows
        ]
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/{attribute_value_id}", response_model=attribute_valueResponse)
async def update_attribute_value(attribute_value_id: int, attribute_value: attribute_valueCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"""
            UPDATE {TABLE_NAME}
            SET attribute_value = :attribute_value,
                attribute_value_desc = :attribute_value_desc,
                remarks = :remarks,
                isactive = :isactive,
                attribute_value_abbr=:attribute_value_abbr,
                nounmodifier_id = :nounmodifier_id
            WHERE attribute_value_id = :attribute_value_id
            RETURNING attribute_value_id, attribute_value, attribute_value_desc, remarks, isactive
        """)
        result = await db.execute(query, {
            "attribute_value_id": attribute_value_id,
            "attribute_value": attribute_value.attribute_value,
            "attribute_value_desc": attribute_value.attribute_value_desc,
            "attribute_value_abbr": attribute_value.attribute_value_abbr,
            "remarks": attribute_value.remarks,
            "isactive": attribute_value.isactive,
            "nounmodifier_id": attribute_value.nounmodifier_id
        })
        await db.commit()

        updated_row = result.fetchone()
        if not updated_row:
            raise HTTPException(status_code=404, detail="attribute_value not found")

        return attribute_valueResponse(**updated_row._asdict(), message="attribute_value updated successfully")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/{attribute_value_id}", response_model=dict)
async def delete_attribute_value(attribute_value_id: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"DELETE FROM {TABLE_NAME} WHERE attribute_value_id = :attribute_value_id")
        result = await db.execute(query, {"attribute_value_id": attribute_value_id})  # Ensure attribute_value_id is passed as a string
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="attribute_value not found")

        return {"message": "attribute_value deleted successfully"}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
