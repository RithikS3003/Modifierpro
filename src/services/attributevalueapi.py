import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from src.db .database import get_db
from src.model.attributevalueschemas import Attribute_valueData, Attribute_valueResponse, Attribute_valueUpdate,attribute_valueCreate
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import List, Optional
import io
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

app = APIRouter()

TABLE_NAME = "attribute_value_master"

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

@app.get("/attribute_values", response_model=Attribute_valueResponse)
async def get_attribute_values(db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "SELECT attribute_value_id, attribute_value, attribute_value_desc, attribute_value_abbr, remarks, isactive, nounmodifier_id "
            "FROM attribute_value_master "
            "ORDER BY attribute_value_id"
        )
        result = await db.execute(query)
        rows = result.fetchall()

        attribute_value = [
            Attribute_valueData(
                attribute_value_id=row[0],
                attribute_value=row[1],
                attribute_value_desc=row[2],
                attribute_value_abbr=row[3],
                remarks=row[4],
                isactive=row[5],
                nounmodifier_id=row[6]
            ) for row in rows
        ]

        return Attribute_valueResponse(message="success", data=attribute_value)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/attribute_value", response_model=Attribute_valueResponse)
async def create_attribute_value(entry: attribute_valueCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Validate that attribute_value is not empty or just whitespace
        if not entry.attribute_value.strip():
            raise HTTPException(status_code=400, detail="Attribute value cannot be an empty string or just whitespace.")

        # Check if the attribute_value already exists to prevent duplicates
        existing_attribute_value = await db.execute(
            text("SELECT 1 FROM attribute_value_master WHERE attribute_value = :attribute_value"),
            {"attribute_value": entry.attribute_value}
        )
        if existing_attribute_value.fetchone():
            raise HTTPException(status_code=400, detail="Attribute value already exists.")

        # Generate new attribute_value_id
        new_attribute_value_id = await generate_attribute_value_id(db)

        # Insert into the database
        query = text("""
            INSERT INTO attribute_value_master (attribute_value_id, attribute_value, attribute_value_desc, remarks, isactive, nounmodifier_id, attribute_value_abbr)
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
            "attribute_value_abbr": entry.attribute_value_abbr
        })
        await db.commit()

        # Fetch and return the inserted values
        inserted_values = result.fetchone()
        return {
            "message": "success",
            "data": [{
                "attribute_value_id": inserted_values[0],
                "attribute_value": inserted_values[1],
                "attribute_value_desc": inserted_values[2],
                "remarks": inserted_values[3],
                "isactive": inserted_values[4],
                "nounmodifier_id": inserted_values[5],
                "attribute_value_abbr": inserted_values[6]
            }]
        }
        return JSONResponse(content=response_data)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Integrity Error: Duplicate attribute_value entry.")
    except SQLAlchemyError as sql_err:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(sql_err)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.put("/AttributeValue/{attribute_value_id}", response_model=Attribute_valueResponse)
async def update_attribute_value(attribute_value_id: str, entry: Attribute_valueUpdate, db: AsyncSession = Depends(get_db)):
    try:
        # Ensure attribute_value_id follows the expected pattern
        if not attribute_value_id.startswith("ATRV_"):
            raise HTTPException(status_code=400, detail="Invalid attribute_value_id format.")

        # Fetch the existing attribute value by attribute_value_id
        existing_attribute_value = await db.execute(
            text(f"SELECT * FROM {TABLE_NAME} WHERE attribute_value_id = :attribute_value_id"),
            {"attribute_value_id": attribute_value_id}
        )
        row = existing_attribute_value.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Attribute value with id {attribute_value_id} not found.")

        # Update the fields that are provided (allow partial updates)
        update_data = {
            "attribute_value": entry.attribute_value if entry.attribute_value else row[1],
            "attribute_value_desc": entry.attribute_value_desc if entry.attribute_value_desc else row[2],
            "remarks": entry.remarks if entry.remarks else row[3],
            "isactive": entry.isactive if entry.isactive is not None else row[4],
            "attribute_value_abbr": entry.attribute_value_abbr if entry.attribute_value_abbr else row[5],
            "nounmodifier_id": entry.nounmodifier_id if entry.nounmodifier_id else row[6]
        }

        # Update the attribute value in the database
        query = text(f"""
            UPDATE {TABLE_NAME}
            SET attribute_value = :attribute_value,
                attribute_value_desc = :attribute_value_desc,
                remarks = :remarks,
                isactive = :isactive,
                attribute_value_abbr = :attribute_value_abbr,
                nounmodifier_id = :nounmodifier_id
            WHERE attribute_value_id = :attribute_value_id
            RETURNING attribute_value_id, attribute_value, attribute_value_desc, remarks, isactive, attribute_value_abbr, nounmodifier_id
        """)
        result = await db.execute(query, {
            "attribute_value_id": attribute_value_id,
            "attribute_value": update_data["attribute_value"],
            "attribute_value_desc": update_data["attribute_value_desc"],
            "remarks": update_data["remarks"],
            "isactive": update_data["isactive"],
            "attribute_value_abbr": update_data["attribute_value_abbr"],
            "nounmodifier_id": update_data["nounmodifier_id"]
        })
        await db.commit()

        updated_row = result.fetchone()
        if not updated_row:
            raise HTTPException(status_code=404, detail="Attribute value not found after update.")

        # Create the response format
        response_data = [
            {
                "attribute_value_id": updated_row[0],
                "attribute_value": updated_row[1],
                "attribute_value_desc": updated_row[2],
                "remarks": updated_row[3],
                "isactive": updated_row[4],
                "attribute_value_abbr": updated_row[5],
                "nounmodifier_id": updated_row[6]
            }
        ]

        return {
            "message": "Attribute value updated successfully",
            "data": response_data  # Return the updated attribute value wrapped in a list
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")




@app.delete("/{attribute_value_id}", response_model=dict)
async def delete_attribute_value(attribute_value_id: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"DELETE FROM {TABLE_NAME} WHERE attribute_value_id = :attribute_value_id")
        result = await db.execute(query, {
            "attribute_value_id": attribute_value_id})  # Ensure attribute_value_id is passed as a string
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="attribute_value not found")

        return {"message": "attribute_value deleted successfully"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))