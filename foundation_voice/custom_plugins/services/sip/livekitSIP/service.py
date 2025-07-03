import os
import time
import random

from livekit import api
from livekit.api import (
    CreateSIPInboundTrunkRequest,
    CreateSIPOutboundTrunkRequest,
    CreateSIPParticipantRequest,
    ListRoomsRequest,
    ListParticipantsRequest,
    ListSIPInboundTrunkRequest, 
    ListSIPOutboundTrunkRequest,
    RoomParticipantIdentity,
    SIPInboundTrunkInfo, 
    SIPOutboundTrunkInfo,
    DeleteSIPTrunkRequest,
)
from google.protobuf.json_format import MessageToDict

from loguru import logger
from typing import Optional, override

from foundation_voice.custom_plugins.services.sip.base_service import SIPService, Stream

class LiveKitSIPService(SIPService):
    def __init__(self):
        super().__init__()
        self.lkapi = None

    async def init(self):
        self.lkapi = api.LiveKitAPI(
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
            url=os.getenv("LIVEKIT_API_URL"),
        )   

    async def create_trunk(
        self, 
        stream: Stream,
        name: str,
        **kwargs
    ):
        trunk = None
        try: 
            
            if stream == Stream.INBOUND:
                trunk_info = SIPInboundTrunkInfo(
                    name=name,
                    numbers=kwargs.get("numbers"),
                )
            
                request = CreateSIPInboundTrunkRequest(
                    trunk=trunk_info,
                )

                trunk = await self.lkapi.sip.create_sip_inbound_trunk(request)

            elif stream == Stream.OUTBOUND:
                trunk_info = SIPOutboundTrunkInfo(
                    name=name,
                    address=kwargs.get("address"),
                    numbers=kwargs.get("numbers"),
                    auth_username=kwargs.get("auth_username"),
                    auth_password=kwargs.get("auth_password"),
                )

                request = CreateSIPOutboundTrunkRequest(
                    trunk=trunk_info,
                )

                trunk = await self.lkapi.sip.create_sip_outbound_trunk(request)

            return MessageToDict(trunk, preserving_proto_field_name=True)

        except Exception as err:
            logger.error(f"Error creating trunk: {err}")
            raise err       


    @override
    async def update_trunk(
        self, 
        stream: Stream,
        trunk_id: str, 
        **fields
    ):
        try: 
            if stream == Stream.INBOUND:
                trunk = await self.lkapi.sip.update_sip_inbound_trunk_fields(trunk_id=trunk_id, **fields)

            elif stream == Stream.OUTBOUND:
                trunk = await self.lkapi.sip.update_sip_outbound_trunk_fields(trunk_id=trunk_id, **fields)

            return MessageToDict(trunk, preserving_proto_field_name=True)

        except Exception as err:
            logger.error(f"Error updating trunk: {err}")
            raise err

    
    @override
    async def delete_trunk(self, trunk_id: str):
        try: 
            request = DeleteSIPTrunkRequest(sip_trunk_id=trunk_id)
            await self.lkapi.sip.delete_sip_trunk(request)
            return {"message": "Trunk deleted"}

        except Exception as err:
            logger.error(f"Error deleting trunk: {err}")
            raise err


    @override
    async def list_trunks(self, stream: Stream):
        try:
            if stream == Stream.INBOUND:
                req = ListSIPInboundTrunkRequest()
                trunks = await self.lkapi.sip.list_sip_inbound_trunk(req)

            elif stream == Stream.OUTBOUND:
                req = ListSIPOutboundTrunkRequest()
                trunks = await self.lkapi.sip.list_sip_outbound_trunk(req)

            return MessageToDict(trunks, preserving_proto_field_name=True)

        except Exception as err:
            logger.error(f"Error listing trunks: {err}")
            raise

    
    async def create_dispatch(
        self,
        trunk_id: str,
        phone_number: str,
        room_name: str,
        participant_identity: Optional[str] = None,
        participant_name: Optional[str] = None,
        krisp_enabled: Optional[bool] = False,
        wait_until_answered: Optional[bool] = True,
    ):
        try: 
            
            logger.info(f"Creating dispatch for trunk_id: {trunk_id}, phone_number: {phone_number}, room_name: {room_name}")

            await self.lkapi.sip.create_sip_participant(
                CreateSIPParticipantRequest(
                    sip_trunk_id=trunk_id,
                    sip_call_to=phone_number,
                    room_name=room_name,
                    participant_identity=participant_identity,
                    participant_name=participant_name,
                    krisp_enabled=krisp_enabled,
                    wait_until_answered=wait_until_answered
                )
            )
            return {"message": "Call dispatched"}
        
        except Exception as err:
            raise err
            

    # Transfer call service
    async def transfer_call(
        self,
        room_name: str,
        transfer_to: str,
        trunk_id: str,
        krisp_enabled: Optional[bool] = False,
        wait_timeout: int = 30,  # seconds
    ):
        participant_identity = f"participant_{random.randint(100, 200)}"
        participant_name = "Support"

        try:
            # Step 1: Dispatch call
            await self.create_dispatch(
                trunk_id=trunk_id,
                phone_number=transfer_to,
                room_name=room_name,
                participant_identity=participant_identity,
                participant_name=participant_name,
                krisp_enabled=krisp_enabled,
                wait_until_answered=True
            )

            # Step 2: Poll until participant joins
            logger.info(f"Waiting for participant {participant_identity} to join...")
            start_time = time.time()
            while time.time() - start_time < wait_timeout:
                room_data = await self.get_room_data(room_name)
                participants = room_data.get("participants", {}).get("participants", [])
                for participant in participants:
                    if participant.get("identity") == participant_identity and participant.get("state") == "ACTIVE":
                        logger.info(f"Participant {participant_identity} has joined the room.")
                        return {"message": "Participant joined"}

                await asyncio.sleep(2)  # small delay between polls

            raise TimeoutError(f"Participant {participant_identity} did not join within {wait_timeout} seconds.")

        except Exception as err:
            logger.error(f"Error transferring call: {err}")
            raise err

    async def get_room_data(self, room_name: str):
        try: 
            req = ListRoomsRequest(names=[room_name])
            rooms = await self.lkapi.room.list_rooms(req)

            req = ListParticipantsRequest(room=room_name) 
            participants = await self.lkapi.room.list_participants(req)

            return {
                "rooms": MessageToDict(rooms, preserving_proto_field_name=True),
                "participants": MessageToDict(participants, preserving_proto_field_name=True)
            }
        
        except Exception as err:
            logger.error(f"Error getting room data: {err}")
            raise err
            

    async def remove_participant(self, room_name: str, identity: str):
        try:
            req = RoomParticipantIdentity(room=room_name, identity=identity)
            await self.lkapi.room.remove_participant(req)
            return {"message": "Agent removed from room"}
        except Exception as err:
            logger.error(f"Error removing participant: {err}")
            raise err

    async def aclose(self):
        await self.lkapi.aclose()