from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base

# Define the base class for the SQLAlchemy models
Base = declarative_base()

# Define the Noun model
class Noun(Base):
    __tablename__ = 'noun_modifier'

    id = Column(Integer, primary_key=True, index=True)
    attribute_id = Column(String, nullable=False)
    abbreviation = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=False)
    nounmodifier_id = Column(String, nullable=False)
