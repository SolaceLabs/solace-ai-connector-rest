import time
import uuid
from queue import Queue, Empty
from uuid import uuid4
from flask import request, Response
from ratelimit import limits, sleep_and_retry
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.common.log import log

from .utils import create_api_response, get_user_info

class UserFormsHandler:
    """Handler for user forms functionality."""
    
    def __init__(self, rest_input):
        """
        Initialize the UserFormsHandler.
        
        Args:
            rest_input: The RestInput instance to access its methods and properties
        """
        self.rest_input = rest_input
        
    def register_routes(self):
        """Register the routes for user forms."""
        
        @self.rest_input.app.route("/api/v1/user_forms", methods=["GET"])
        @sleep_and_retry
        @limits(self.rest_input.rate_limit, self.rest_input._rate_limit_time_period)
        def user_forms_handler():
            user_id = "default"
            user_email = "default"
            if self.rest_input.authentication_enabled:
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    return create_api_response("No token provided", 400)

                token_id = auth_header.split("Bearer ")[1]

                # authenticate by the token
                resp, status_code = get_user_info(self.rest_input.authentication_server, token_id)
                log.debug(f"Authentication response code: {status_code}")
                if status_code != 200:
                    return create_api_response(
                        "Authentication failed.",
                        status_code,
                    )
                log.debug("Successfully logged in.")

                user_id = resp["user_id"]
                user_email = resp["email"]
            server_input_id = str(uuid4())

            response_queue = Queue()
            self.rest_input.kv_store_set(
                f"server_input:{server_input_id}:response_queue", response_queue
            )

            session_id = str(uuid.uuid4())

            payload = {
                "event_type": "get_pending_forms",
                "user_id": user_id,
                "user_email": user_email,
                "stream": False,
                "session_id": session_id,
            }

            user_properties = {
                "server_input_id": server_input_id,
                "user_id": user_id,
                "user_email": user_email,
                "session_id": session_id,
                "timestamp": time.time(),
                "input_type": "rest_api",
                "use_history": False,
            }

            message = Message(payload=payload, user_properties=user_properties)
            message.set_previous(payload)
            event = Event(EventType.MESSAGE, message)
            self.rest_input.process_event_with_tracing(event)
            log.debug(f"Sent event to solace agent mesh: {event}.")

            return self.generate_user_form_response(server_input_id, response_queue)
            
    def generate_user_form_response(
        self, server_input_id: int, response_queue: Queue
    ) -> Response:
        """
        Generate a response for user forms.
        
        Args:
            server_input_id: The server input ID
            response_queue: The queue to get the response from
            
        Returns:
            Response: The HTTP response
        """
        # TODO: add a timeout to the response queue
        form_response = {}
        while not self.rest_input.stop_signal.is_set():
            try:
                response = response_queue.get(timeout=1)
            except Empty:
                continue

            log.debug(f"Getting response: {response}")
            form_response = response
            break

        return create_api_response(form_response, 200)