import uvicorn
# from catalogue_core.src.db import database  # This import should be here
from src.nounmodifier import app as noun_modifier
from src.modifierapi import app as modi_app
from src.Nounapi import app as noun_app
from src.manufacturer import app as manufacturer
from src.attributevalue import app as attribute_value
from fastapi import FastAPI, Depends

app = FastAPI()

app.mount("/master_modifier", modi_app)
app.mount("/master_noun", noun_app)
app.mount("/master_noun_modifier", noun_modifier)
app.mount("/master_manufacturer", manufacturer)
app.mount("/master_attribute_value", attribute_value)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
