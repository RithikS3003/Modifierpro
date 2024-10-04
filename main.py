import uvicorn
from src .modifierapi import app as modi_app
from src .Nounapi import app as noun_app
from fastapi import FastAPI

app = FastAPI()

app.mount("/master_modifier", modi_app)
app.mount("/master_noun", noun_app)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)