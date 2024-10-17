from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.db .database import get_db
from src.model.nounmodifierschemas import NounModifierCreate,NounModifierUpdate, NounModifierData, NounModifierResponse
from typing import List
import pandas as pd
import io
from fastapi.responses import StreamingResponse

app = APIRouter()

TABLE_NAME = "nounmodifier_combined"


async def get_existing_noun_id(db: AsyncSession) -> str:
    query = text("SELECT noun_id FROM noun_mstr ORDER BY noun_id DESC LIMIT 1")
    result = await db.execute(query)
    return result.scalar() or "N_0000"  # Return a default if not found

async def get_existing_modifier_id(db: AsyncSession) -> str:
    query = text("SELECT modifier_id FROM modifier_mstr ORDER BY modifier_id DESC LIMIT 1")
    result = await db.execute(query)
    return result.scalar() or "M_0000"  # Return a default if not found


# Helper function to increment IDs like "N_0990", "M_0990"
def increment_id(existing_id: str) -> str:
    prefix, num_part = existing_id.split('_')
    new_number = int(num_part) + 1
    return f"{prefix}_{new_number:04d}"  # Maintain format with leading zeros

# Generate new nounmodifier_id based on the last one in the table
async def generate_nounmodifier_id(db: AsyncSession) -> str:
    query = text(f"SELECT nounmodifier_id FROM nounmodifier_combined ORDER BY nounmodifier_id DESC LIMIT 1")
    result = await db.execute(query)
    last_nounmodifier_id = result.scalar()

    if last_nounmodifier_id is not None:
        prefix, num_part = last_nounmodifier_id.split('_')
        new_id_number = int(num_part) + 1
        return f"{prefix}_{new_id_number:04d}"  # Maintain format with leading zeros
    else:
        return "NM_0001"  # Start from NM_0001 if no entries exist

@app.get("/NounModifier", response_model=NounModifierResponse)
async def get_noun_values(db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"""
            SELECT noun_id,modifier_id, noun,modifier,abbreviation,description,isactive,nounmodifier_id,noun_modifier
            FROM {TABLE_NAME}
            ORDER BY nounmodifier_id
        """)
        result = await db.execute(query)
        rows = result.fetchall()

        # Map the fetched rows to the NounResponse model
        nounmodifiers = [NounModifierData(
            noun_id=row[0],
            modifier_id=row[1],
            noun=row[2],
            modifier=row[3],
            abbreviation=row[4],
            description=row[5],
            isactive=row[6],
            nounmodifier_id=row[7],
            noun_modifier=row[8]

        ) for row in rows]

        return NounModifierResponse(message="success", data=nounmodifiers)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




@app.post("/NounModifier", response_model=NounModifierResponse)
async def create_nounmodifier(entry: NounModifierCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Validate that neither noun nor modifier is empty
        if not entry.noun.strip() or not entry.modifier.strip():
            raise HTTPException(status_code=400, detail="Noun or Modifier cannot be an empty string or just whitespace")

        # Retrieve the latest noun_id and modifier_id
        existing_noun_id = await get_existing_noun_id(db)  # Fetch last noun_id
        existing_modifier_id = await get_existing_modifier_id(db)  # Fetch last modifier_id

        # Increment noun_id and modifier_id
        new_noun_id = increment_id(existing_noun_id)
        new_modifier_id = increment_id(existing_modifier_id)

        # Generate new nounmodifier_id
        new_nounmodifier_id = await generate_nounmodifier_id(db)

        # Insert into nounmodifier_combined table
        query = text(f"""
            INSERT INTO {TABLE_NAME} (nounmodifier_id, noun, modifier, abbreviation, description, isactive, noun_id, modifier_id)
            VALUES (:nounmodifier_id, :noun, :modifier, :abbreviation, :description, :isactive, :noun_id, :modifier_id)
            RETURNING nounmodifier_id, noun, modifier, abbreviation, description, isactive, noun_id, modifier_id
        """)
        result = await db.execute(query, {
            "nounmodifier_id": new_nounmodifier_id,
            "noun": entry.noun,
            "modifier": entry.modifier,
            "abbreviation": entry.abbreviation,
            "description": entry.description,
            "isactive": entry.isactive,
            "noun_id": new_noun_id,
            "modifier_id": new_modifier_id,
        })
        await db.commit()

        inserted_values = result.fetchone()

        response_data = {
            "message": "success",
            "data": [{
                "nounmodifier_id": inserted_values[0],
                "noun": inserted_values[1],
                "modifier": inserted_values[2],
                "abbreviation": inserted_values[3],
                "description": inserted_values[4],
                "isactive": inserted_values[5],
                "noun_id": inserted_values[6],
                "modifier_id": inserted_values[7]
            }]
        }
        return JSONResponse(content=response_data)

    except IntegrityError as ie:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Integrity Error: {str(ie)}")
    except SQLAlchemyError as sql_err:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(sql_err)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")



# Updating an existing noun
@app.put("/NounModifier/{nounmodifier_id}", response_model=NounModifierResponse)
async def update_nounmodifier(nounmodifier_id: str, entry: NounModifierUpdate, db: AsyncSession = Depends(get_db)):
    try:
        # Fetch the existing noun modifier by nounmodifier_id
        existing_noun_modifier = await db.execute(
            text(f"SELECT * FROM {TABLE_NAME} WHERE nounmodifier_id = :nounmodifier_id"),
            {"nounmodifier_id": nounmodifier_id}
        )
        row = existing_noun_modifier.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"NounModifier with id {nounmodifier_id} not found.")

        # Update the fields that are provided (allow partial updates)
        update_data = {
            "noun": entry.noun if entry.noun is not None else row[1],
            "modifier": entry.modifier if entry.modifier is not None else row[2],
            "abbreviation": entry.abbreviation if entry.abbreviation is not None else row[3],
            "description": entry.description if entry.description is not None else row[4],
            "isactive": entry.isactive if entry.isactive is not None else row[5]
        }

        # Update the noun modifier in the database
        query = text(f"""
            UPDATE {TABLE_NAME}
            SET noun = :noun, modifier = :modifier, abbreviation = :abbreviation, description = :description, isactive = :isactive
            WHERE nounmodifier_id = :nounmodifier_id
            RETURNING nounmodifier_id, noun, modifier, abbreviation, description, isactive
        """)
        result = await db.execute(query, {
            "nounmodifier_id": nounmodifier_id,
            "noun": update_data["noun"],
            "modifier": update_data["modifier"],
            "abbreviation": update_data["abbreviation"],
            "description": update_data["description"],
            "isactive": update_data["isactive"]
        })
        await db.commit()

        updated_row = result.fetchone()

        # Create the response format
        response_data = {
            "noun_id": nounmodifier_id,  # Assuming noun_id corresponds to nounmodifier_id
            "modifier_id": nounmodifier_id,  # Update with the correct modifier_id if it's different
            "nounmodifier_id": updated_row[0],
            "noun": updated_row[1],
            "modifier": updated_row[2],
            "abbreviation": updated_row[3],
            "description": updated_row[4],
            "isactive": updated_row[5]
        }

        return {
            "message": "NounModifier updated successfully",
            "data": [response_data]  # Return the updated noun modifier as a list
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")






# Deleting a noun using noun_id
@app.delete("/NounModifier/{nounmodifier_id}", response_model=dict)
async def delete_nounmodifier(nounmodifier_id: str, db: AsyncSession = Depends(get_db)):
    try:
        query_check = text(f"""
            SELECT nounmodifier_id
            FROM {TABLE_NAME}
            WHERE nounmodifier_id = :nounmodifier_id
        """)
        result_check = await db.execute(query_check, {"nounmodifier_id": nounmodifier_id})
        nounmodifier = result_check.fetchone()

        if not nounmodifier:
            raise HTTPException(status_code=404, detail="NounModifier not found")

        query_delete = text(f"""
            DELETE FROM {TABLE_NAME}
            WHERE nounmodifier_id = :nounmodifier_id
        """)
        await db.execute(query_delete, {"nounmodifier_id": nounmodifier_id})
        await db.commit()

        return {"message": "NounModifier entry deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# Upload an Excel file containing nouns
@app.post("/upload-excel")
async def upload_excel(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        df = pd.read_excel(file.file)

        if 'noun' not in df.columns:
            raise HTTPException(status_code=400, detail="Excel file must contain a 'noun' column")

        async with db.begin():  # Use transaction
            for index, row in df.iterrows():
                noun_value = row['noun']
                if pd.isna(noun_value) or not noun_value.strip():
                    continue  # Skip empty rows

                query_check = text(f"""
                    SELECT noun_id
                    FROM {TABLE_NAME}
                    WHERE noun = :noun
                """)
                result_check = await db.execute(query_check, {"noun": noun_value})
                existing_noun = result_check.fetchone()

                if existing_noun:
                    query_update = text(f"""
                        UPDATE {TABLE_NAME}
                        SET noun = :noun
                        WHERE noun_id = :noun_id
                    """)
                    await db.execute(query_update, {"noun": noun_value, "noun_id": existing_noun[0]})
                else:
                    new_noun_id = await generate_nounmodifier_id(db)  # Generate new noun_id
                    query_insert = text(f"""
                        INSERT INTO {TABLE_NAME} (noun_id, noun)
                        VALUES (:noun_id, :noun)
                    """)
                    await db.execute(query_insert, {"noun_id": new_noun_id, "noun": noun_value})

        await db.commit()
        return {"message": "Excel file processed successfully."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))



@app.get("/export-excel")
async def export_excel(db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"""
            SELECT noun_id, noun
            FROM {TABLE_NAME}
            ORDER BY noun_id
        """)
        result = await db.execute(query)
        rows = result.fetchall()

        df = pd.DataFrame(rows, columns=["noun_id", "noun"])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Nouns')

        output.seek(0)  # Rewind the buffer to the beginning

        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": "attachment; filename=nouns.xlsx"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))