# 1. Create a new noun (POST method)
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from schemas import NounCreate, NounUpdate, NounResponse, ModifierData, ModifierResponse
from database import get_db
from typing import List

# Initialize FastAPI app
app = FastAPI()



# Helper function to generate the next custom ID
async def generate_custom_id(db: AsyncSession) -> int:
    last_noun = await db.execute(text("SELECT id FROM noun_modifier ORDER BY id DESC LIMIT 1"))
    last_id = last_noun.fetchone()

    if last_id is None:  # Check if there are no existing entries
        new_id = 1  # Start from 1 if the table is empty
    else:
        new_id = last_id[0] + 1  # Increment the last ID by 1

    return new_id  # Return the new ID as an integer

async def generate_modifier_id(db: AsyncSession) -> str:
    query = text(f"SELECT attribute_id FROM noun_modifier ORDER BY attribute_id DESC LIMIT 1")
    result = await db.execute(query)
    last_modifier_id = result.scalar()

    if last_modifier_id is not None:
        # Extract the numeric part of the modifier_id
        try:
            prefix, num_part = last_modifier_id.split('_')
            if prefix != 'M':
                raise HTTPException(status_code=500, detail=f"Unexpected modifier_id prefix: {prefix}")

            new_id_number = int(num_part) + 1
            return f"{prefix}_{new_id_number:04d}"  # Ensuring 4 digits format
        except ValueError:
            raise HTTPException(status_code=500, detail=f"Invalid modifier_id format: {last_modifier_id}")
    else:
        return "M_0001"  # If no entries, start with "M_0001"

@app.post("/nouns", response_model=ModifierResponse)
async def create_noun(entry: NounCreate, db: AsyncSession = Depends(get_db)) -> NounResponse:
    try:
        print(f"Received entry: {entry.abbreviation}, {entry.description}")

        # Generate custom ID and modifier ID
        # custom_id = await generate_custom_id(db)
        modifier_id = await generate_modifier_id(db)

        # Insert the new noun into the database with generated IDs
        insert_query = text("""
            INSERT INTO noun_modifier ( attribute_id, abbreviation, description, nounmodifier_id)
            VALUES ( :attribute_id, :abbreviation, :description, :nounmodifier_id)
            RETURNING attribute_id, abbreviation, description, nounmodifier_id;
        """)
        print(insert_query)

        # Executing the query with proper parameter binding
        result = await db.execute(
            insert_query, {
                # "id": custom_id,
                "attribute_id": modifier_id,
                "abbreviation": entry.abbreviation,
                "description": entry.description,
                "nounmodifier_id": entry.nounmodifier_id  # Keep as integer if valid
            }
        )
        await db.commit()

        # Fetch the newly inserted row and return it as the response
        new_noun = result.fetchone()

        if new_noun is None:
            raise HTTPException(status_code=500, detail="Failed to create noun.")

        print(f"Successfully created noun: {new_noun}")

        # Return the newly created noun detailss
        return NounResponse(

            attribute_id=new_noun.attribute_id,
            abbreviation=new_noun.abbreviation,
            description=new_noun.description,
            nounmodifier_id=new_noun.nounmodifier_id
        )

    except IntegrityError:
        await db.rollback()
        print("Integrity Error: Duplicate entry.")
        raise HTTPException(status_code=400, detail="Integrity Error: Duplicate entry.")
    except SQLAlchemyError as e:
        await db.rollback()
        print(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        await db.rollback()
        print(f"Internal Server Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# 3. Get noun by ID (GET method)
@app.get("/nouns/{attribute_id}", response_model=ModifierResponse)
async def get_noun(attribute_id: str, db: AsyncSession = Depends(get_db)) -> ModifierResponse:
    try:
        # Perform the SQL query to fetch the noun modifiers
        result = await db.execute(
            text(
                "SELECT attribute_id, nounmodifier_id, abbreviation, description FROM noun_modifier WHERE attribute_id = :attribute_id"),
            {'attribute_id': attribute_id}
        )

        # Fetch all matching rows
        rows = result.fetchall()

        # If no rows are returned, raise a 404 error
        if not rows:
            raise HTTPException(status_code=404, detail="Noun not found.")

        # Map the result rows to the ModifierData response model
        modifiers = [
            ModifierData(
                attribute_id=row[0],  # attribute_id (column 0)
                nounmodifier_id=row[1],  # nounmodifier_id (column 1)
                abbreviation=row[2],  # abbreviation (column 2)
                description=row[3]  # description (column 3)
            )
            for row in rows
        ]

        # Return the ModifierResponse
        return ModifierResponse(message="success", data=modifiers)

    except Exception as e:
        # Catch all exceptions and return a 400 Bad Request
        raise HTTPException(status_code=400, detail=str(e))

# Example of another endpoint to get modifiers
@app.get("/Modifier", response_model=ModifierResponse)
async def get_noun_values(db: AsyncSession = Depends(get_db)):
    try:
        query = text("""
            SELECT attribute_id, nounmodifier_id, abbreviation, description
            FROM noun_modifier  
            ORDER BY attribute_id
        """)
        result = await db.execute(query)
        rows = result.fetchall()

        # Map the fetched rows to the ModifierData model
        modifiers = [ModifierData(
            attribute_id=row[0],  # Adjust based on actual column index for modifier_id
            nounmodifier_id=row[1],  # Adjust based on actual column index for modifier
            abbreviation=row[2],  # Adjust based on actual column index for abbreviation
            description=row[3]  # Adjust based on actual column index for description
        ) for row in rows]

        return ModifierResponse(message="success", data=modifiers)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
#
@app.put("/nouns/{attribute_id}", response_model=ModifierResponse)
async def update_noun(attribute_id: str, entry: NounUpdate, db: AsyncSession = Depends(get_db)) -> ModifierResponse:
    try:
        # Fetch the noun by attribute_id to check if it exists
        result_check = await db.execute(
            text("SELECT attribute_id, abbreviation, description, nounmodifier_id FROM noun_modifier WHERE attribute_id = :attribute_id"),
            {"attribute_id": attribute_id}
        )
        noun = result_check.fetchone()

        if not noun:
            raise HTTPException(status_code=404, detail="Noun not found.")

        # Check if abbreviation is provided and if it already exists in another record
        if entry.abbreviation:
            existing_abbreviation_check = await db.execute(
                text("SELECT 1 FROM noun_modifier WHERE abbreviation = :abbreviation AND attribute_id != :attribute_id"),
                {"abbreviation": entry.abbreviation, "attribute_id": attribute_id}
            )
            if existing_abbreviation_check.fetchone():
                raise HTTPException(status_code=400, detail="Abbreviation already exists.")

        # Proceed with updating the record, keeping existing values if not provided
        update_query = text("""
            UPDATE noun_modifier
            SET abbreviation = :abbreviation,
                description = :description,
                nounmodifier_id = :nounmodifier_id
            WHERE attribute_id = :attribute_id
            RETURNING attribute_id, abbreviation, description, nounmodifier_id;
        """)
        updated_result = await db.execute(update_query, {
            "attribute_id": attribute_id,
            "abbreviation": entry.abbreviation or noun[1],  # Keep existing value if not provided
            "description": entry.description or noun[2],    # Keep existing value if not provided
            "nounmodifier_id": entry.nounmodifier_id or noun[3]  # Keep existing value if not provided
        })
        await db.commit()

        updated_noun_data = updated_result.fetchone()

        # Ensure the updated data exists and is valid
        if not updated_noun_data:
            raise HTTPException(status_code=404, detail="Noun not updated.")

        # Return the updated data in the correct format
        return ModifierResponse(
            message="success",
            data=[ModifierData(
                attribute_id=updated_noun_data[0],
                nounmodifier_id=updated_noun_data[3],
                abbreviation=updated_noun_data[1],
                description=updated_noun_data[2]
            )]
        )

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# 5. Delete a noun (DELETE method)
@app.delete("/nouns/{attribute_id}")
async def delete_noun(attribute_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result_check = await db.execute(text("SELECT * FROM noun_modifier WHERE attribute_id = :attribute_id;"), {"attribute_id": attribute_id})
        noun = result_check.fetchone()
        if not noun:
            raise HTTPException(status_code=404, detail="Noun not found.")

        await db.execute(text("DELETE FROM noun_modifier WHERE attribute_id = :attribute_id;"), {"attribute_id": attribute_id})
        await db.commit()

        return {"message": f"Noun with ID {attribute_id} deleted successfully."}

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
