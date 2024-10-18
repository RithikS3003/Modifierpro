from fastapi import FastAPI
from database import get_db
from crud import create_noun, get_noun, update_noun, delete_noun, get_noun_values
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

app = FastAPI()

# Routes
app.add_api_route("/create-noun", create_noun, methods=["POST"])
app.add_api_route("/Modifier", get_noun_values, methods=["GET"])
app.add_api_route("/noun/{attribute_id}", get_noun, methods=["GET"])
app.add_api_route("/noun/{attribute_id}", update_noun, methods=["PUT"])
app.add_api_route("/noun/{attribute_id}", delete_noun, methods=["DELETE"])
