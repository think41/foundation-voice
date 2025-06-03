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


contexts = {
    "MagicalNestContext": MagicalNestContext
}