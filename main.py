import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.services.nounapi import app as noun_router
from src.services.nounmodifierapi import app as nounmodifier_router
from src.services.modifierapi import app as modifier_router
from src.services.attributenameapi import app as attributename_router
from src.services.attributevalueapi import app as attributevalue_router
from src.services.manufactureapi import app as manufacture_router
from src.db.database import engine, Base

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the  router
app.include_router(noun_router, prefix="/Noun", tags=["Noun"])
app.include_router(nounmodifier_router, prefix="/NounModifier", tags=["NounModifier"])
app.include_router(modifier_router, prefix="/Modifier", tags=["Modifier"])
app.include_router(attributename_router,prefix="/Attributename",tags=["Attributename"])
app.include_router(attributevalue_router,prefix="/Attributevalue",tags=["Attributevalue"])
app.include_router(manufacture_router,prefix="/Manufacure",tags=["Manufacure"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)







    # Create tables
# @app.on_event("startup")
# async def startup():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
