import random

from loguru import logger
from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException

from foundation_voice.custom_plugins.services.sip.livekitSIP.service import Stream, LiveKitSIPService

sip_service = None
async def get_service_instance():
    global sip_service
    if sip_service is None:
        sip_service = LiveKitSIPService()
        await sip_service.init()
    return sip_service


router = APIRouter()

def get_commons(request: Request):
    return {
        "cai_sdk": request.app.state.cai_sdk,
        "defined_agents": request.app.state.defined_agents
    }

# Trunk logic route
@router.post("/create-trunk")
async def create_trunk(
    request: Request,
    sip: LiveKitSIPService = Depends(get_service_instance)
):
    try:
        data = await request.json()
        stream = Stream(data.get("stream"))
        name = data.get("name")
        trunk_fields = data.get("trunk_fields")
    
        trunk = await sip.create_trunk(stream, name, **trunk_fields)
        return trunk
    except Exception as err:
        logger.error(f"Error creating trunk: {err}")
        raise err
    

@router.patch("/update-trunk")
async def update_trunk(
    request: Request,
    sip: LiveKitSIPService = Depends(get_service_instance)
):
    try:
        data = await request.json()
        stream = Stream(data.get("stream"))
        trunk_id = data.get("trunk_id")
        trunk_fields = data.get("trunk_fields")

        response = await sip.update_trunk(stream, trunk_id, **trunk_fields)
        return response
    except Exception as err:
        logger.error(f"Error updating trunk: {err}")
        raise err

@router.delete("/delete-trunk")
async def delete_trunk(
    request: Request,
    sip: LiveKitSIPService = Depends(get_service_instance)
):
    try:
        data = await request.json()
        trunk_id = data.get("trunk_id")
        response = await sip.delete_trunk(trunk_id)
        return response
    except Exception as err:
        logger.error(f"Error deleting trunk: {err}")
        raise err

@router.get("/list-trunks")
async def list_trunks(
    request: Request,
    sip: LiveKitSIPService = Depends(get_service_instance)
):
    try:
        data = await request.json()
        stream = Stream(data.get("stream"))
        trunks = await sip.list_trunks(stream)
        return trunks
    except Exception as err:
        logger.error(f"Error listing trunks: {err}")
        raise err


# Call dispatch route
@router.post("/dispatch-call")
async def dispatch_call(
    request: Request,
    background_tasks: BackgroundTasks,
    sip: LiveKitSIPService = Depends(get_service_instance),
    commons: dict = Depends(get_commons)
):
    data = await request.json()

    call_options = data.get("call_options")
    data.pop("call_options")

    cai_sdk = commons.get("cai_sdk")
    defined_agents = commons.get("defined_agents")
    
    if not cai_sdk or not defined_agents:
        raise HTTPException(status_code=400, detail="cai_sdk or defined_agents not found in commons")

    agent_name = data.get("agent_name")
    agent = defined_agents.get(agent_name)
    session_id = data.get("session_id")
    metadata = data.get("metadata")

    if metadata is None:
        metadata = {}

    response = await cai_sdk.connect_handler(data, agent, session_id=session_id, metadata=metadata)

    participant_identity = f"participant_{random.randint(0, 100)}"
    participant_name = "User"
    try:        
        await sip.create_dispatch(
            trunk_id=call_options.get("trunk_id"),
            phone_number=call_options.get("phone_number"),
            room_name=response.get("room_name"),
            participant_identity=participant_identity,
            participant_name=participant_name,
            krisp_enabled=call_options.get("krisp_enabled", False),
            wait_until_answered=call_options.get("wait_until_answered", True)
        )


        if "background_task_args" in response:
            task_args = response.pop("background_task_args")
            func = task_args.pop("func")
            background_tasks.add_task(func, **task_args)


        logger.info(f"Trunk ID: {call_options.get('trunk_id')}, room_name: {response.get('room_name')}")
        metadata["room_name"] = response.get("room_name")
        metadata["trunk_id"] = call_options.get("trunk_id")
        metadata["transfer_to"] = call_options.get("transfer_to")
        
        return {"message": "Call dispatched"}
    except Exception as err:
        logger.error(f"Error dispatching call: {err}")
        return {"error": str(err)}


# Transfer call route
@router.post("/transfer-call")
async def transfer_call(
    request: Request,
    sip: LiveKitSIPService = Depends(get_service_instance)
):
    try:
        data = await request.json()
        room_name = data.get("room_name")
        participant_identity = data.get("participant_identity")
        transfer_to = data.get("transfer_to")

        response = await sip.transfer_call(room_name, participant_identity, transfer_to)
        return response
    except Exception as err:
        logger.error(f"Error transferring call: {err}")
        raise err
