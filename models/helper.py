import uuid
from sqlmodel import SQLModel, Field, Relationship
# ---------------------------
# Helper: Short UUID generator
# ---------------------------
def short_uuid() -> str:
    """Generate a short 5-char UUID string"""
    return str(uuid.uuid4())[:5]


# ---------------------------
# Config for Pydantic v2 good model
# ---------------------------
class ConfiguredBase(SQLModel):
    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "arbitrary_types_allowed": True,
    }
