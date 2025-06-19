from typing import Optional
from pydantic import BaseModel

"""

Define your agent context here

Example:
class AgentContext(BaseModel):
    placeholder1: str
    placeholder2: int

"""


class MagicalNestContext(BaseModel):
    name: str | None = None
    age: int | None = None
    gender: str | None = None
    room_type: str | None = None
    colors: str | None = None
    activities: str | None = None
    themes: str | None = None
    constraints: str | None = None
    products: str | None = None

class LeapScholarContext(BaseModel):
    country: Optional[str] = None
    intake: Optional[str] = None
    program: Optional[str] = None
    passport: Optional[str] = None
    education: Optional[str] = None
    grades: Optional[str] = None
    ielts_status: Optional[str] = None
    current_location: Optional[str] = None


contexts = {
    "MagicalNestContext": MagicalNestContext,
    "LeapScholarContext": LeapScholarContext
}
