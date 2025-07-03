from loguru import logger 

from livekit.api import ListRoomsRequest
from pipecat.frames.frames import TTSSpeakFrame

from foundation_voice.custom_plugins.services.sip.livekitSIP.router import get_service_instance

def get_agent_participant(participants: list[dict]) -> dict | None:
    for participant in participants:
        if participant.get("permission", {}).get("agent") is True:
            return participant
    return None

async def transfer_call(
    room_name: str, 
    trunk_id: str,
    transfer_to: str,
    **kwargs
):
    """
    Use this tool to transfer the call to another participant only in livekit room and if you have the room_name parameter.
    Only call this tool if the user explicitly mentions to transfer the call to another participant or
    if you don't have the context to help the user further.

    You'll be given the room_name, transfer_to and participant_identity as context.
    

    Args: 
        room_name: str 
        Room name of the livekit room

        trunk_id: str
        Trunk ID of the SIP trunk 

        transfer_to: str 
        Transfer the call to this number 
    """
    logger.info(f"params: {kwargs}")
    llm = kwargs["llm"]
    await llm.push_frame(TTSSpeakFrame("Please hold while we transfer the call"))
    logger.info(f"Transfer call: {room_name}, {trunk_id}, {transfer_to}")
    try:
        sip_service = await get_service_instance()
        room_data = await sip_service.get_room_data(room_name)
        agent_participant = get_agent_participant(room_data["participants"]["participants"])

        logger.info(f"Agent participant: {agent_participant}")

        response = await sip_service.transfer_call(
            room_name=room_name, 
            trunk_id=trunk_id, 
            transfer_to=transfer_to
        )

        await sip_service.remove_participant(
            room_name=room_name,
            identity=agent_participant["identity"]
        )

        return MessageToDict(response, preserving_proto_field_name=True)

        # await kwargs["result_callback"](response)
    except Exception as err:
        await llm.push_frame(TTSSpeakFrame(f"It seems there was some issue transfering the call. You can try again or I continue conversing with you."))
        logger.error(f"Error transferring call: {err}")
        raise err   
    


inhouse_tools = {
    "transfer_call": transfer_call
}