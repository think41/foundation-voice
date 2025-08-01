from fastapi import APIRouter, HTTPException

from foundation_voice.models.schemas import AgentRequest, AgentResponse
from foundation_voice.services.agent_services import AgentGenerationService
from foundation_voice.utils.file_generator import FileGenerator
from loguru import logger

router = APIRouter()
agent_service = AgentGenerationService()
file_generator = FileGenerator()


@router.post("/generate-agent", response_model=AgentResponse)
async def generate_agent(request: AgentRequest):
    """Generate a voice agent based on user prompt"""
    try:
        # Validate agent type
        if request.agent_type not in ["single", "multi"]:
            raise HTTPException(
                status_code=400, detail="agent_type must be either 'single' or 'multi'"
            )

        logger.info("Request received")
        # Generate agent configuration and Python file
        agent_config, python_content = await agent_service.generate_agent(
            request.user_prompt,
            request.agent_type,
            request.additional_info,
            request.guardrails,
        )

        logger.info("Agent config generated")
        return AgentResponse(
            agent_config=agent_config,
            python_file_content=python_content,
            agent_type=request.agent_type,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating agent: {str(e)}")


# @router.post("/generate-agent-files")
# async def generate_agent_files(request: AgentRequest):
#     """Generate agent files and return as downloadable zip"""
#     try:
#         # Generate the agent
#         response = await generate_agent(request)

#         # Create zip file
#         zip_buffer = file_generator.create_zip_file(
#             response.agent_config,
#             response.python_file_content,
#             response.agent_type
#         )

#         # Generate filename
#         filename = file_generator.generate_filename(
#             response.agent_config,
#             response.agent_type
#         )

#         return StreamingResponse(
#             BytesIO(zip_buffer.read()),
#             media_type="application/zip",
#             headers={"Content-Disposition": f"attachment; filename={filename}"}
#         )

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error generating agent files: {str(e)}")

# @router.get("/health")
# async def health_check():
#     """Health check endpoint"""
#     return {
#         "status": "healthy",
#         "timestamp": datetime.now().isoformat(),
#         "service": "Voice Agent Generator API"
#     }
