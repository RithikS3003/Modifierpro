from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Define the base class for the SQLAlchemy models
Base = declarative_base()

# Define your PostgreSQL database URL
DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/postgres"

# Create the asynchronous engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Create a session factory bound to the engine
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Dependency to get the database session
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
#
# # Define the Noun model
# class Noun(Base):
#     __tablename__ = 'noun_mstr'
#
#     id = Column(Integer, primary_key=True, index=True)
#     attribute_id = Column(Integer, nullable=False)
#     abbreviation = Column(String, unique=True, nullable=False)
#     description = Column(String, nullable=False)
#     nounmodifier_id = Column(Integer, ForeignKey('nounmodifier_mstr.id'), nullable=False)
#
#     # You can add additional methods or properties here if needed
