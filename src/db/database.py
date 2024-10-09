# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# from sqlalchemy.orm import sessionmaker
# from starlette.middleware.cors import CORSMiddleware
# from catalogue_core.src.Nounapi import app
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# # Database connection details
# DATABASE_URL = "postgresql+asyncpg://postgres:postgres@192.168.0.190:5432/tagminds"
#
# # Create the async engine and session
# engine = create_async_engine(DATABASE_URL, echo=True)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
#
# async def get_db():
#     async with SessionLocal() as session:
#         try:
#             yield session
#         finally:
#             await session.close()