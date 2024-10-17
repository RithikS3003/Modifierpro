import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from src.db .database import get_db
from src.model.manufactureschemas import ManufacturerCreate, ManufacturerData, ManufacturerResponse,ManufacturerUpdate
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import List, Optional
import io
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

app = APIRouter()

TABLE_NAME = "manufacturer_master"

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

@app.get("/manufacturers", response_model=ManufacturerResponse)
async def get_manufacturers(db: AsyncSession = Depends(get_db)):
    try:
        query = text(
            "SELECT manufacturid, manufacturname, manufacturdesc, remarks, isactive, nounmodifier_id "
            "FROM manufacturer_master "
            "ORDER BY manufacturid"
        )
        result = await db.execute(query)
        rows = result.fetchall()

        # Map the fetched rows to the ManufacturerData model
        manufacturers = [
            ManufacturerData(
                manufacturid=str(row[0]),  # Ensure it is a string
                manufacturname=row[1],
                manufacturdesc=row[2],
                remarks=str(row[3]) if row[3] is not None else "",  # Ensure remarks is a string
                isactive=bool(row[4]),  # Convert to boolean
                nounmodifier_id=str(row[5])  # Ensure it is a string
                # manufacturer_abbr=str(row[6]) if row[6] is not None else ""  # Ensure abbr is a string
            ) for row in rows
        ]

        # Return the structured response
        return ManufacturerResponse(message="success", data=manufacturers)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@app.post("/manufacturer")
async def create_manufacturer(entry: ManufacturerCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Generate new manufacturid
        new_manufacturid = await generate_manufacturid(db)

        # Validate that manufacturname is not empty or just whitespace
        if not entry.manufacturname.strip():
            raise HTTPException(status_code=400, detail="Manufacturer name cannot be an empty string or just whitespace")

        # Check if the manufacturer already exists
        existing_manufacturer = await db.execute(
            text("SELECT 1 FROM manufacturer_master WHERE manufacturname = :manufacturname"),
            {"manufacturname": entry.manufacturname}
        )
        if existing_manufacturer.fetchone():
            raise HTTPException(status_code=400, detail="Manufacturer already exists.")

        # Insert into the database
        query = text("""
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

        # Generate manufacturer abbreviation (e.g., first 3 characters of name or leave empty if not required)
        manufacturer_abbr = manufacturname[:3].upper()

        # Return the response in the desired format
        return {
            "message": "success",
            "data": [
                {
                    "manufacturid": manufacturid,
                    "manufacturname": manufacturname,
                    "manufacturdesc": manufacturdesc,
                    "remarks": remarks,
                    "isactive": isactive,
                    "nounmodifier_id": nounmodifier_id,
                    # "manufacturer_abbr": manufacturer_abbr  # or "" if you want it empty
                }
            ]
        }

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Integrity Error: Duplicate manufacturer entry.")
    except SQLAlchemyError as sql_err:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(sql_err)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.put("/Manufacturer/{manufacturid}", response_model=ManufacturerResponse)
async def update_manufacturer(manufacturid: str, manufacturer: ManufacturerUpdate, db: AsyncSession = Depends(get_db)):
    try:
        # Fetch the existing manufacturer by manufacturid
        existing_manufacturer = await db.execute(
            text(f"SELECT * FROM {TABLE_NAME} WHERE manufacturid = :manufacturid"),
            {"manufacturid": manufacturid}
        )
        row = existing_manufacturer.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Manufacturer with id {manufacturid} not found.")

        # Update the fields that are provided (allow partial updates)
        update_data = {
            "manufacturname": manufacturer.manufacturname if manufacturer.manufacturname is not None else row[1],
            "manufacturdesc": manufacturer.manufacturdesc if manufacturer.manufacturdesc is not None else row[2],
            "remarks": manufacturer.remarks if manufacturer.remarks is not None else row[3],
            "isactive": manufacturer.isactive if manufacturer.isactive is not None else row[4],
            "nounmodifier_id": manufacturer.nounmodifier_id if manufacturer.nounmodifier_id is not None else row[5]
            # "manufacturer_abbr": row[6]  
        }

        # Update the manufacturer in the database
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
            "manufacturname": update_data["manufacturname"],
            "manufacturdesc": update_data["manufacturdesc"],
            "remarks": update_data["remarks"],
            "isactive": update_data["isactive"],
            "nounmodifier_id": update_data["nounmodifier_id"]
        })
        await db.commit()

        updated_row = result.fetchone()

        if not updated_row:
            raise HTTPException(status_code=404, detail="Manufacturer not found")

        # Prepare the response data
        response_data = {
            "manufacturid": updated_row[0],
            "manufacturname": updated_row[1],
            "manufacturdesc": updated_row[2],
            "remarks": updated_row[3],
            "isactive": updated_row[4],
            # "manufacturer_abbr": updated_row[5],  # Include manufacturer_abbr in response
            "nounmodifier_id": update_data["nounmodifier_id"]
        }

        return {
            "message": "Manufacturer updated successfully",
            "data": [response_data]  # Return as a list
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")




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