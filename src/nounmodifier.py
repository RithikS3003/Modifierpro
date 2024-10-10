import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, modifier
from typing import List, Optional
import io
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Initialize the FastAPI app
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


# Table name
TABLE_NAME = "nounmodifier_combined"


# Pydantic models
class NounModifierCreate(BaseModel):
    # noun_id: str
    # modifier_id: str
    noun: str
    modifier:str
    abbreviation: str
    description: str
    isactive: bool
    # noun_modifier_id: str
    message: Optional[str]
class NounModifierUpdate(BaseModel):
    noun_id: str
    modifier_id: str
    noun: str
    modifier:str
    abbreviation: str
    description: str
    isactive: bool
    nounmodifier_id: str
    # message: Optional[str]
class NounModifierResponse(BaseModel):
    noun_id: str
    modifier_id: str
    noun: str
    modifier:str
    abbreviation: str
    description: str
    isactive: bool
    nounmodifier_id: str
    message: Optional[str]  # Add a message field for responses


# Function to generate new noun_id based on existing entries
# async def generate_nounmodifier_id(db: AsyncSession) -> str:
#     query = text(f"SELECT nounmodifier_id FROM {TABLE_NAME} ORDER BY nounmodifier_id DESC LIMIT 1")
#     result = await db.execute(query)
#     last_nounmodifier_id = result.scalar()
#
#     if last_nounmodifier_id is not None:
#         # Extract the numeric part of the noun_id
#         try:
#             prefix, num_part = last_nounmodifier_id.split('_')
#             new_id_number = int(num_part) + 1
#             return f"{prefix}_{new_id_number}"  # Return the new noun_id in the same format
#         except ValueError:
#             raise HTTPException(status_code=500, detail=f"Invalid nounmodifier_id format: {last_nounmodifier_id}")
#     else:
#         return "NM_1"  # If no entries, start with "N_1"

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

@app.get("/NounModifier", response_model=List[NounModifierResponse])
async def get_noun_values(db: AsyncSession = Depends(get_db)):
    try:
        query = text(f"""
            SELECT noun_id,modifier_id, noun,modifier,abbreviation,description,isactive,nounmodifier_id
            FROM {TABLE_NAME}
            ORDER BY nounmodifier_id
        """)
        result = await db.execute(query)
        rows = result.fetchall()

        # Map the fetched rows to the NounResponse model
        nouns = [NounModifierResponse(
            noun_id=row[0],
            modifier_id=row[1],
            noun=row[2],
            modifier=row[3],
            abbreviation=row[4],
            description=row[5],
            isactive=row[6],
            nounmodifier_id=row[7],
            message="ok"  # Explicitly setting message to None or remove this line
        ) for row in rows]

        return nouns
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# def increment_id(existing_id: str) -> str:
#     # Example: existing_id = "N_0989"
#     prefix, num_part = existing_id.split('_')
#     new_number = int(num_part) + 1
#     return f"{prefix}_{new_number:04d}"  # Maintain format with leading zeros


@app.post("/NounModifier", response_model=NounModifierResponse)
async def create_nounmodifier(entry: NounModifierCreate, db: AsyncSession = Depends(get_db)):
    try:
        if not entry.nounmodifier.strip():
            raise HTTPException(status_code=400, detail="NounModifier cannot be an empty string or just whitespace")

        # Retrieve the latest noun_id and modifier_id
        existing_noun_id = await get_existing_noun_id(db)  # Fetch last noun_id
        existing_modifier_id = await get_existing_modifier_id(db)  # Fetch last modifier_id

        # Increment noun_id and modifier_id
        new_noun_id = increment_id(existing_noun_id)
        new_modifier_id = increment_id(existing_modifier_id)

        # Generate new nounmodifier_id
        new_nounmodifier_id = await generate_nounmodifier_id(db)

        # Insert into nounmodifier_combined
        query = text(f"""
            INSERT INTO{TABLE_NAME} (nounmodifier_id, noun,modifier,abbreviation, description, isactive noun_id, modifier_id)
            VALUES (:nounmodifier_id, :noun,modifier, :abbreviation, :description, :isactive :noun_id, :modifier_id)
            RETURNING nounmodifier_id, noun,modifier, abbreviation, description, isactive,noun_id, modifier_id
        """)
        result = await db.execute(query, {
            "nounmodifier_id": new_nounmodifier_id,
            "noun": entry.noun,
            "modifier":entry.modifier,
            "noun_id": new_noun_id,
            "abbreviation":entry.abbreviation,
            "description":entry.description,
            "isactive":entry.isactive,
            "modifier_id": new_modifier_id,
        })
        await db.commit()

        # Fetching inserted values
        inserted_nounmodifier_id, inserted_noun,inserted_modifier, inserted_abbreviation,inserted_description,inserted_isactive,inserted_noun_id, inserted_modifier_id = result.fetchone()

        return {
            "noun_id": inserted_noun_id,
            "modifier_id": inserted_modifier_id,
            "noun": inserted_noun,
            "modifier":inserted_modifier,
            "abbreviation": inserted_abbreviation,
            "description": inserted_description,
            "isactive":inserted_isactive,
            "nounmodifier_id": inserted_nounmodifier_id,
            "message": "NounModifier Created successfully"
        }

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
        # Fetch the existing noun by noun_id
        existing_noun = await db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE nounmodifier_id = :nounmodifier_id"), {"nounmodifier_id": nounmodifier_id})
        row = existing_noun.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Noun with id {nounmodifier_id} not found.")

        # Update the fields that are provided (allow partial updates)
        update_data = {
            "noun": entry.noun if entry.noun else row[1],
            "modifier":entry.modifier if entry.modifier else row[2],
            "abbreviation": entry.abbreviation if entry.abbreviation else row[3],
            "description": entry.description if entry.description else row[4],
            "isactive": entry.isactive if entry.isactive is not None else row[5]
        }

        # Update the noun in the database
        query = text(f"""
            UPDATE {TABLE_NAME}
            SET nounmodifier = :noun,modifier, abbreviation = :abbreviation, description = :description, isactive = :isactive
            WHERE nounmodifier_id = :nounmodifier_id    
            RETURNING nounmodifier_id, noun, abbreviation, description, isactive
        """)
        result = await db.execute(query, {
            "nounmodifier_id": nounmodifier_id,
            "nounmodifier": update_data["nounmodifier"],
            "abbreviation": update_data["abbreviation"],
            "description": update_data["description"],
            "isactive": update_data["isactive"]
        })
        await db.commit()

        updated_row = result.fetchone()

        return {
            "nounmodifier_id": updated_row[0],
            "nounmodifier": updated_row[1],
            "abbreviation": updated_row[2],
            "description": updated_row[3],
            "isactive": updated_row[4],
            "message": "Noun updated successfully"
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


# Export noun data to an Excel file
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


# Run the app using: uvicorn main:app --reload


# Updating an existing noun
@app.put("/Noun/{noun_id}", response_model=NounModifierResponse)
async def update_noun(noun_id: str, entry: NounModifierUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query_check = text(f"""
            SELECT noun_id, noun
            FROM {TABLE_NAME}
            WHERE noun_id = :noun_id
        """)
        result_check = await db.execute(query_check, {"noun_id": noun_id})
        noun = result_check.fetchone()

        if not noun:
            raise HTTPException(status_code=404, detail="Noun not found")

        query_update = text(f"""
            UPDATE {TABLE_NAME}
            SET noun = :noun
            WHERE noun_id = :noun_id
            RETURNING noun_id, noun
        """)
        result_update = await db.execute(query_update, {"noun": entry.noun, "noun_id": noun_id})
        await db.commit()

        updated_noun = result_update.fetchone()
        if updated_noun is None:
            raise HTTPException(status_code=400, detail="Failed to update noun")

        updated_noun_id, updated_noun_value = updated_noun
        return NounModifierResponse(noun_id=updated_noun_id, noun=updated_noun_value, message="Noun entry updated successfully")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


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


# Export noun data to an Excel file
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


# Run the app using: uvicorn main:app --reload

# Run the app with uvicorn main:app --reload
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="127.0.0.1", port=8000)
