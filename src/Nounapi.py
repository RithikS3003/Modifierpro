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
from starlette.responses import JSONResponse

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
TABLE_NAME = "noun_mstr"


# Pydantic models
class NounCreate(BaseModel):
    noun: str
    abbreviation: str
    description: str
    isactive: bool
    # message: Optional[str]
class NounUpdate(BaseModel):
    noun: str
    abbreviation: str
    description: str
    isactive: bool
    # message: Optional[str]
class NounData(BaseModel):
    noun_id: str
    noun: str
    abbreviation: str
    description: str
    isactive: bool
class NounResponse(BaseModel):
    message: str
    data: List[NounData] # Add a message field for responses


# Function to generate new noun_id based on existing entries
async def generate_noun_id(db: AsyncSession) -> str:
    query = text(f"SELECT noun_id FROM {TABLE_NAME} ORDER BY noun_id DESC LIMIT 1")
    result = await db.execute(query)
    last_noun_id = result.scalar()

    if last_noun_id is not None:
        # Extract the numeric part of the noun_id
        try:
            prefix, num_part = last_noun_id.split('_')
            new_id_number = int(num_part) + 1
            return f"{prefix}_{new_id_number}"  # Return the new noun_id in the same format
        except ValueError:
            raise HTTPException(status_code=500, detail=f"Invalid noun_id format: {last_noun_id}")
    else:
        return "N_1"  # If no entries, start with "N_1"

@app.get("/Noun", response_model=NounResponse)
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
            raise HTTPException(status_code=400, detail="Noun cannot be an empty string or just whitespace")

        # Check if the noun already exists
        existing_noun = await db.execute(text(f"SELECT 1 FROM {TABLE_NAME} WHERE noun = :noun"), {"noun": entry.noun})
        if existing_noun.fetchone():
            raise HTTPException(status_code=400, detail="Noun already exists.")

        # Generate a new noun_id
        new_noun_id = await generate_noun_id(db)

        # Insert into the table with the generated noun_id
        query = text(f"""
            INSERT INTO {TABLE_NAME} (noun_id, noun, abbreviation, description, isactive)
            VALUES (:noun_id, :noun, :abbreviation, :description, :isactive)
            RETURNING noun_id, noun, abbreviation, description, isactive
        """)
        result = await db.execute(query, {
            "noun_id": new_noun_id,
            "noun": entry.noun,
            "abbreviation": entry.abbreviation,
            "description": entry.description,
            "isactive": entry.isactive
        })
        await db.commit()

        # Fetching inserted values
        inserted_noun_id, inserted_noun, inserted_abbreviation, inserted_description, inserted_isactive = result.fetchone()

        response_data = {
            "message": "success",
            "data": [{
                "noun_id": inserted_noun_id,
                "noun": inserted_noun,
                "abbreviation": inserted_abbreviation,
                "description": inserted_description,
                "isactive": inserted_isactive
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
                    new_noun_id = await generate_noun_id(db)  # Generate new noun_id
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
@app.put("/Noun/{noun_id}", response_model=NounResponse)
async def update_noun(noun_id: str, entry: NounUpdate, db: AsyncSession = Depends(get_db)):
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
        return NounResponse(noun_id=updated_noun_id, noun=updated_noun_value, message="Noun entry updated successfully")
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
                    new_noun_id = await generate_noun_id(db)  # Generate new noun_id
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
