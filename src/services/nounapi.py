from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.db .database import get_db
from src.model.nounschemas import NounCreate,NounData, NounUpdate, NounResponse
from typing import List
import pandas as pd
import io
from fastapi.responses import StreamingResponse

app = APIRouter()

TABLE_NAME = "noun_mstr"


async def generate_noun_id(db: AsyncSession):
    # Query to fetch the latest noun_id
    result = await db.execute(text("SELECT noun_id FROM noun_mstr ORDER BY noun_id DESC LIMIT 1"))
    last_id = result.fetchone()

    if last_id:
        # Extract the numeric part from the noun_id (e.g., 'N_0989' -> 989)
        last_numeric_id = int(last_id[0].split('_')[1])
        new_numeric_id = last_numeric_id + 1
    else:
        new_numeric_id = 1  # Start from 1 if no records exist

    # Create new noun_id in the format 'N_XXXX'
    new_noun_id = f"N_{new_numeric_id:04d}"
    return new_noun_id


@app.get("/", response_model=NounResponse)
async def get_noun_values(db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"""
            SELECT noun_id, noun, abbreviation, description, isactive
            FROM {TABLE_NAME}
            ORDER BY noun_id
        """)
        result = await db.execute(query)
        rows = result.fetchall()

        # Map the fetched rows to the NounData model
        nouns = [NounData(
            noun_id=row[0],
            noun=row[1],
            abbreviation=row[2],
            description=row[3],
            isactive=row[4]
        ) for row in rows]

        return NounResponse(message="success", data=nouns)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/Noun", response_model=NounResponse)
async def create_noun(entry: NounCreate, db: AsyncSession = Depends(get_db)):
    try:
        if not entry.noun.strip():
            raise HTTPException(status_code=400, detail="Noun cannot be empty")

        # Check for existing noun
        existing_query = text("SELECT 1 FROM noun_mstr WHERE noun = :noun")
        result = await db.execute(existing_query, {"noun": entry.noun})
        if result.scalar():
            raise HTTPException(status_code=400, detail="Noun already exists")

        # Generate new noun_id
        new_noun_id = await generate_noun_id(db)

        # Insert query
        insert_query = text("""
            INSERT INTO noun_mstr (noun_id, noun, abbreviation, description, isactive)
            VALUES (:noun_id, :noun, :abbreviation, :description, :isactive)
            RETURNING noun_id, noun, abbreviation, description, isactive
        """)
        
        result = await db.execute(
            insert_query,
            {
                "noun_id": new_noun_id,
                "noun": entry.noun,
                "abbreviation": entry.abbreviation,
                "description": entry.description,
                "isactive": entry.isactive
            }
        )
        
        await db.commit()
        
        row = result.fetchone()
        response_data = {
            "message": "success",
            "data": [{
                "noun_id": row[0],
                "noun": row[1],
                "abbreviation": row[2],
                "description": row[3],
                "isactive": row[4]
            }]
        }
        
        return JSONResponse(content=response_data)
        
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Updating an existing noun
@app.put("/Noun/{noun_id}", response_model=NounResponse)
async def update_noun(noun_id: str, entry: NounUpdate, db: AsyncSession = Depends(get_db)):
    try:
        # Fetch the existing noun by noun_id
        existing_noun = await db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE noun_id = :noun_id"), {"noun_id": noun_id})
        row = existing_noun.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Noun with id {noun_id} not found.")

        # Update the fields that are provided (allow partial updates)
        update_data = {
            "noun": entry.noun if entry.noun else row[1],
            "abbreviation": entry.abbreviation if entry.abbreviation else row[2],
            "description": entry.description if entry.description else row[3],
            "isactive": entry.isactive if entry.isactive is not None else row[4]
        }

        # Update the noun in the database
        query = text(f"""
            UPDATE {TABLE_NAME} 
            SET noun = :noun, abbreviation = :abbreviation, description = :description, isactive = :isactive
            WHERE noun_id = :noun_id
            RETURNING noun_id, noun, abbreviation, description, isactive
        """)
        result = await db.execute(query, {
            "noun_id": noun_id,
            "noun": update_data["noun"],
            "abbreviation": update_data["abbreviation"],
            "description": update_data["description"],
            "isactive": update_data["isactive"]
        })
        await db.commit()

        updated_row = result.fetchone()

        # Create the response format
        response_data = [
            {
                "noun_id": updated_row[0],
                "noun": updated_row[1],
                "abbreviation": updated_row[2],
                "description": updated_row[3],
                "isactive": updated_row[4]
            }
        ]

        return {
            "message": "Noun updated successfully",
            "data": response_data  # Return the updated noun in a list
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# Deleting a noun using noun_id
@app.delete("/Noun/{noun_id}", response_model=dict)
async def delete_noun(noun_id: str, db: AsyncSession = Depends(get_db)):
    try:
        query_check = text(f"""
            SELECT noun_id
            FROM {TABLE_NAME}
            WHERE noun_id = :noun_id
        """)
        result_check = await db.execute(query_check, {"noun_id": noun_id})
        noun = result_check.fetchone()

        if not noun:
            raise HTTPException(status_code=404, detail="Noun not found")

        query_delete = text(f"""
            DELETE FROM {TABLE_NAME}
            WHERE noun_id = :noun_id
        """)
        await db.execute(query_delete, {"noun_id": noun_id})
        await db.commit()

        return {"message": "Noun entry deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))