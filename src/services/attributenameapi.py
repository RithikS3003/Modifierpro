from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine 
from src.db .database import get_db
from src.model.attributenameschemas import AttributeCreate,AttributeData, AttributeResponse, AttributeUpdate
from typing import List
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import List, Optional
import io
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

app = APIRouter()

TABLE_NAME = "attribute_master"

async def generate_attribute_id(db: AsyncSession):
    result = await db.execute(text("SELECT MAX(attribute_id) FROM attribute_master"))
    last_id = result.scalar()  # Get the last id from the database

    # Extract the number part from the last_id
    if last_id:
        number_part = int(last_id.split('_')[1])  # Assuming the format is ATR_XXXX
        new_number_part = number_part + 1
    else:
        new_number_part = 1  # Start from 1 if there's no entry

    return f"ATR_{new_number_part:04d}"  # Format it as ATR_XXXX


async def get_existing_nounmodifier_id(db: AsyncSession) -> str:
    query = text("SELECT nounmodifier_id FROM attribute_master ORDER BY attribute_id DESC LIMIT 1")
    result = await db.execute(query)
    return result.scalar() or "NM_0000"  # Return a default if not found

# Helper function to increment IDs like "N_0990", "M_0990"
def increment_id(existing_id: str) -> str:
    prefix, num_part = existing_id.split('_')
    new_number = int(num_part) + 1
    return f"{prefix}_{new_number:04d}"  # Maintain format with leading zeros

@app.get("/Attribute", response_model=AttributeResponse)
async def get_noun_values(db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"""
            SELECT attribute_id,nounmodifier_id, attribute_name,abbreviation,description,isactive
            FROM {TABLE_NAME}
            ORDER BY attribute_id
        """)
        result = await db.execute(query)
        rows = result.fetchall()

        # Map the fetched rows to the NounResponse model
        attributes = [AttributeData(
            attribute_id=row[0],
            nounmodifier_id=row[1],
            attribute_name=row[2],
            abbreviation=row[3],
            description=row[4],
            isactive=row[5]
           # Explicitly setting message to None or remove this line
        ) for row in rows]

        return AttributeResponse(message="success", data=attributes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/Attribute", response_model=AttributeResponse)
async def create_attributename(entry: AttributeCreate, db: AsyncSession = Depends(get_db)):
    try:
        if not entry.attribute_name.strip():
            raise HTTPException(status_code=400, detail="Attribute cannot be an empty string or just whitespace")

        existing_attribute_name = await db.execute(
            text(f"SELECT 1 FROM {TABLE_NAME} WHERE attribute_name = :attribute_name"),
            {"attribute_name": entry.attribute_name}
        )
        if existing_attribute_name.fetchone():
            raise HTTPException(status_code=400, detail="attribute_name already exists.")

        existing_nounmodifier_id = await get_existing_nounmodifier_id(db)

        new_nounmodifier_id = increment_id(existing_nounmodifier_id)

        # Generate the new attribute_id in the format ATR_XXXX
        new_attribute_id = await generate_attribute_id(db)

        query = text(f"""
            INSERT INTO {TABLE_NAME} (attribute_id, nounmodifier_id, attribute_name, abbreviation, description, isactive)
            VALUES (:attribute_id, :nounmodifier_id, :attribute_name, :abbreviation, :description, :isactive)
            RETURNING attribute_id, nounmodifier_id, attribute_name, abbreviation, description, isactive
        """)
        result = await db.execute(query, {
            "attribute_id": new_attribute_id,
            "nounmodifier_id": new_nounmodifier_id,
            "attribute_name": entry.attribute_name,
            "abbreviation": entry.abbreviation,
            "description": entry.description,
            "isactive": entry.isactive
        })
        await db.commit()

        inserted_values = result.fetchone()
        return {
            "message": "success",
            "data": [{
                "attribute_id": inserted_values[0],
                "nounmodifier_id": inserted_values[1],
                "attribute_name": inserted_values[2],
                "abbreviation": inserted_values[3],
                "description": inserted_values[4],
                "isactive": inserted_values[5]

            }]
        }
        return JSONResponse(content=response_data)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Integrity Error: Duplicate noun entry.")
    except SQLAlchemyError as sql_err:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(sql_err)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")



# Updating an existing noun
@app.put("/Attribute/{attribute_id}", response_model=AttributeResponse)
async def update_attribute_name(attribute_id: str, entry: AttributeUpdate, db: AsyncSession = Depends(get_db)):
    try:
        # Fetch the existing attribute by attribute_id
        existing_attribute = await db.execute(
            text(f"SELECT * FROM {TABLE_NAME} WHERE attribute_id = :attribute_id"),
            {"attribute_id": attribute_id}
        )
        row = existing_attribute.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Attribute with id {attribute_id} not found.")

        # Update the fields that are provided (allow partial updates)
        update_data = {
            "attribute_name": entry.attribute_name if entry.attribute_name else row[1],
            "abbreviation": entry.abbreviation if entry.abbreviation else row[2],
            "description": entry.description if entry.description else row[3],
            "isactive": entry.isactive if entry.isactive is not None else row[4]
        }

        # Update the attribute in the database
        query = text(f"""
            UPDATE {TABLE_NAME} 
            SET attribute_name = :attribute_name, abbreviation = :abbreviation, description = :description, isactive = :isactive
            WHERE attribute_id = :attribute_id
            RETURNING attribute_id, attribute_name, abbreviation, description, isactive
        """)
        result = await db.execute(query, {
            "attribute_id": attribute_id,
            "attribute_name": update_data["attribute_name"],
            "abbreviation": update_data["abbreviation"],
            "description": update_data["description"],
            "isactive": update_data["isactive"]
        })
        await db.commit()

        updated_row = result.fetchone()

        # Create the response format
        response_data = [
            {
                "attribute_id": updated_row[0],
                "nounmodifier_id": row[5],  # Assuming you have this in the original row
                "attribute_name": updated_row[1],
                "abbreviation": updated_row[2],
                "description": updated_row[3],
                "isactive": updated_row[4]
            }
        ]

        return {
            "message": "Attribute updated successfully",
            "data": response_data  # Return the updated attribute in a list
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")



# Deleting a noun using noun_id
@app.delete("/Attribute/{attribute_id}", response_model=dict)
async def delete_noun(attribute_id: str, db: AsyncSession = Depends(get_db)):
    try:
        query_check = text(f"""
            SELECT attribute_id
            FROM {TABLE_NAME}
            WHERE attribute_id = :attribute_id
        """)
        result_check = await db.execute(query_check, {"attribute_id": attribute_id})
        noun = result_check.fetchone()

        if not noun:
            raise HTTPException(status_code=404, detail="Noun not found")

        query_delete = text(f"""
            DELETE FROM {TABLE_NAME}
            WHERE attribute_id = :attribute_id
        """)
        await db.execute(query_delete, {"attribute_id": attribute_id})
        await db.commit()

        return {"message": "AttributeName entry deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))