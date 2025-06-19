from typing import Dict, Any
from agent_configure.utils.context import LeapScholarContext

_session_contexts = {}
def get_or_create_context(session_id: str):
    if session_id not in _session_contexts:
        _session_contexts[session_id] = LeapScholarContext()
    return _session_contexts[session_id]

def update_user_profile(session_id: str, key: str, value: str) -> Dict[str, Any]:
    """Update user profile information"""
    try:
        context = get_or_create_context(session_id)
        # ctx.context is a LeapScholarContext object, need to use setattr
        setattr(context, key, value)
        # Check if all required fields are filled
        profile_complete = all(getattr(context, field) is not None for field in [
            'country', 'intake', 'program', 'passport', 
            'education', 'grades', 'ielts_status', 'current_location'
        ])
        return {
            "success": True,
            "updated_field": key,
            "value": value,
            "profile_complete": profile_complete
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

    
def handoff_to_advisor(context: LeapScholarContext, call_sid: str) -> Dict[str, Any]:
    """
    Handoff qualified student to human advisor using conference for reliable transfer.
    """
    global twilio_client

    if not context:
        context = get_or_create_context(session_id)
    
    logger.info(f"Handoff initiated for AI agent call SID: {call_sid}")
    
    try:
        # Step 1: Initialize Twilio client if needed
        if twilio_client is None:
            logger.info("Initializing Twilio client")
            if not (os.getenv('TWILIO_ACCOUNT_SID') and os.getenv('TWILIO_AUTH_TOKEN')):
                error_msg = "Twilio credentials not found in environment variables"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "requires_continuation": True}
            
            try:
                twilio_client = Client(
                    os.getenv('TWILIO_ACCOUNT_SID'),
                    os.getenv('TWILIO_AUTH_TOKEN')
                )
                logger.info("Twilio client initialized successfully")
            except Exception as e:
                error_msg = f"Failed to initialize Twilio client: {str(e)}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "requires_continuation": True}

        # Step 2: Validate environment variables and current call
        advisor_phone = os.getenv('ADVISOR_PHONE_NUMBER')
        twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not advisor_phone or not twilio_phone:
            error_msg = "Missing required environment variables: ADVISOR_PHONE_NUMBER or TWILIO_PHONE_NUMBER"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "requires_continuation": True}

        # Verify customer call is still active
        try:
            customer_call = twilio_client.calls(call_sid).fetch()
            if customer_call.status != 'in-progress':
                error_msg = f"Customer call is not active (status: {customer_call.status})"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "requires_continuation": True}
        except Exception as e:
            logger.error(f"Failed to verify customer call status: {e}")
            return {"success": False, "error": str(e), "requires_continuation": True}

        # Step 3: Generate profile summary for advisor
        profile_summary = ""
        if ctx and hasattr(ctx, 'context') and ctx.context:
            profile_summary = (
                f"Student from {getattr(ctx.context, 'current_location', 'unknown location')} "
                f"wants to study {getattr(ctx.context, 'program', 'unknown program')} "
                f"in {getattr(ctx.context, 'country', 'unknown country')}. "
                f"Intake: {getattr(ctx.context, 'intake', 'unknown')}. "
                f"IELTS: {getattr(ctx.context, 'ielts_status', 'unknown')}."
            )
            logger.debug(f"Generated profile summary: {profile_summary}")

        try:
            # Step 4: Create persistent conference
            conference_name = f"leap-advisor-{call_sid[-12:]}"
            logger.info(f"Setting up persistent conference: {conference_name}")
            
            # Put customer on hold with clear message
            holding_twiml = VoiceResponse()
            holding_twiml.say(
                "Please hold while I connect you with our advisor. This may take a moment.",
                voice='alice'
            )
            holding_twiml.play(url="http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical")
            
            try:
                logger.info("Putting customer on hold")
                twilio_client.calls(call_sid).update(twiml=str(holding_twiml))
                time.sleep(1)  # Give time for hold message to play
            except Exception as e:
                logger.error(f"Failed to put customer on hold: {e}")
                return {"success": False, "error": str(e), "requires_continuation": True}
            
            # Create persistent conference and move customer
            conference_result = create_persistent_conference(call_sid, conference_name)
            if not conference_result["success"]:
                logger.error("Failed to create persistent conference")
                prevent_call_termination(call_sid)
                return {
                    "success": False,
                    "error": conference_result["error"],
                    "requires_continuation": True,
                    "prevent_termination": True
                }
            
            # Verify customer joined conference
            customer_conf = ensure_conference_connection(conference_name, call_sid)
            if not customer_conf["success"]:
                logger.error("Failed to confirm customer in conference")
                prevent_call_termination(call_sid)
                return {
                    "success": False,
                    "error": "Customer failed to join conference",
                    "requires_continuation": True,
                    "prevent_termination": True
                }
            
            # Call advisor
            logger.info(f"Initiating advisor call to {advisor_phone}")
            advisor_twiml = VoiceResponse()
            advisor_twiml.say(
                f"New student transfer. {profile_summary} "
                "Press any key when ready to connect.",
                voice='alice'
            )
            
            gather = advisor_twiml.gather(
                num_digits=1,
                timeout=10,
                action=os.getenv('GATHER_ACTION_URL')
            )
            
            advisor_call = twilio_client.calls.create(
                to=advisor_phone,
                from_=twilio_phone,
                twiml=str(advisor_twiml),
                status_callback=os.getenv('CALL_STATUS_CALLBACK_URL'),
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST',
                timeout=30
            )
            logger.info(f"Advisor call initiated with SID: {advisor_call.sid}")
            
            # Monitor advisor call status
            advisor_status = monitor_call_status(advisor_call.sid, timeout=45)
            if not advisor_status["success"]:
                logger.error(f"Advisor call failed: {advisor_status['error']}")
                prevent_call_termination(call_sid)
                return {
                    "success": False,
                    "error": f"Advisor unavailable: {advisor_status['error']}",
                    "requires_continuation": True,
                    "should_retry": True,
                    "prevent_termination": True
                }
            
            # Connect advisor to conference
            advisor_conference_twiml = VoiceResponse()
            dial = advisor_conference_twiml.dial(hangup_on_star=False)
            dial.conference(
                conference_name,
                start_conference_on_enter=True,
                end_conference_on_exit=True,
                beep=False
            )
            
            twilio_client.calls(advisor_call.sid).update(twiml=str(advisor_conference_twiml))
            logger.info("Advisor connected to conference")
            
            # Verify both parties are in conference
            final_status = check_conference_status(conference_name)
            if not final_status.get("exists") or final_status.get("participants", 0) < 2:
                logger.error("Failed to confirm both parties in conference")
                prevent_call_termination(call_sid)
                return {
                    "success": False,
                    "error": "Failed to establish conference connection",
                    "requires_continuation": True,
                    "prevent_termination": True
                }
            
            # Success - both parties are connected
            return {
                "success": True,
                "transferred_to": "human_advisor",
                "transfer_method": "conference",
                "conference_name": conference_name,
                "advisor_call_sid": advisor_call.sid,
                "persistent_call_sid": conference_result["persistent_call_sid"],
                "conference_status": final_status,
                "ai_agent_status": "transfer_complete",
                "message": "Transfer completed successfully",
                "requires_continuation": False,  # We can disconnect since the conference is persistent
                "prevent_termination": True
            }
            
        except Exception as e:
            logger.error(f"Conference setup failed: {str(e)}")
            prevent_call_termination(call_sid)
            
            # Attempt graceful recovery
            try:
                recovery_twiml = VoiceResponse()
                recovery_twiml.say(
                    "I apologize, but I'm having trouble connecting you to an advisor. "
                    "I'll continue assisting you, or we can try again shortly.",
                    voice='alice'
                )
                twilio_client.calls(call_sid).update(twiml=str(recovery_twiml))
                
                return {
                    "success": False,
                    "error": f"Conference setup failed: {str(e)}",
                    "requires_continuation": True,
                    "should_retry": True,
                    "prevent_termination": True,
                    "message": "Failed to setup conference, recovered back to AI agent"
                }
                
            except Exception as e2:
                logger.error(f"Recovery also failed: {str(e2)}")
                return {
                    "success": False,
                    "error": f"Both conference and recovery failed: {str(e2)}",
                    "requires_continuation": True,
                    "prevent_termination": True
                }
            
    except Exception as e:
        logger.error(f"Handoff failed for call {call_sid}: {str(e)}")
        prevent_call_termination(call_sid)
        return {
            "success": False,
            "error": str(e),
            "requires_continuation": True,
            "prevent_termination": True
        }


tools = {
    "update_user_profile": update_user_profile,
    "handoff_to_advisor": handoff_to_advisor,
}