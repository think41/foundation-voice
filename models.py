from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    message: str = Field(..., description="Status message indicating API health")


class WebRTCResponse(BaseModel):
    pc_id: str = Field(..., description="Unique identifier for the WebRTC connection")
    sdp: str = Field(..., description="Session Description Protocol data")
    type: str = Field(..., description="Type of WebRTC message (answer)")
