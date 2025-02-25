import time
import json
import uuid
from queue import Queue, Empty
from typing import Any, Dict, Generator
from uuid import uuid4
from werkzeug.utils import secure_filename
from flask import request, Response
from ratelimit import limits, sleep_and_retry
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.common.log import log

from .rest_base import RestBase, info as base_info
from .utils import create_api_response, get_user_info

# Clone and modify the info dictionary
info = base_info.copy()
info.update(
    {
        "class_name": "RestInput",
        "description": "This component receives REST API requests and prepare them for cognitive mesh processing.",
    }
)

info["config_parameters"].extend(
    [
        {
            "name": "rest_input",
            "type": "object",
            "properties": {
                "authentication": {  # Configure the authentication
                    "type": "object",
                    "properties": {
                        "enabled": {
                            "type": "boolean",
                            "description": "Flag to enable authentication.",
                            "required": True,
                        },
                        "server": {  # Disabled authentication does not need this
                            "type": "string",
                            "description": "The URL of the authentication server.",
                            "required": False,
                        },
                    },
                },
                "host": {
                    "type": "string",
                    "description": "The host address.",
                    "required": True,
                    "default": "127.0.0.1",
                },
                "endpoint": {
                    "type": "string",
                    "description": "The API endpoint that is assigned to the interface.",
                    "required": True,
                },
                "rate_limit": {
                    "type": "number",
                    "description": ("Maximum rate of requests per seconds."),
                    "required": False,
                    "default": 1000000,
                },
            },
            "description": "REST API configuration parameters.",
        },
    ],
)

info["input_schema"] = {
    "type": "object",
    "properties": {
        "request": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt to send to the cognitive mesh.",
                },
                "stream": {
                    "type": "boolean",
                    "description": "A flag that indicates whether the response should be streamed.",
                },
                "session_id": {
                    "type": "string",
                    "description": "The session ID for the request.",
                },
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                            },
                            "content": {
                                "type": "string",
                            },
                            "mime_type": {"type": "string"},
                            "url": {
                                "type": "string",
                            },
                            "size": {
                                "type": "number",
                            },
                        },
                    },
                },
            },
            "required": ["prompt", "stream"],
        },
    },
}


info["output_schema"] = {
    "type": "object",
    "properties": {
        "event": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The response from cognitive mesh.",
                },
                "user_email": {
                    "type": "string",
                    "description": "The email of the user.",
                },
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user.",
                },
                "timestamp": {
                    "type": "string",
                    "description": "The timestamp of the event.",
                },
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "description": "Files to download.",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL of the file.",
                            },
                        },
                    },
                },
            },
            "required": ["text", "user_email", "user_id", "timestamp"],
        },
    },
}


class RestInput(RestBase):
    """Component that receives REST API requests and prepares them for cognitive mesh processing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.listen_port = self.get_config("listen_port", 5050)


    def register_routes(self):
        """Register the routes for the REST API server."""

        self._rate_limit_time_period = 60  # in seconds
        self.endpoint = self.get_config("endpoint", "/api/v1/request")
        self.rate_limit = int(self.get_config("rate_limit", 100))

        self.authentication = self.get_config("authentication", {})
        self.authentication_enabled = self.authentication.get("enabled", False)
        if self.authentication_enabled:
            self.authentication_server = self.authentication.get("server")

        @self.app.route(self.endpoint, methods=["POST"])
        @sleep_and_retry
        @limits(self.rate_limit, self._rate_limit_time_period)
        def request_handler():
            prompt = request.form.get("prompt")
            stream = request.form.get("stream")
            session_id = request.form.get("session_id")

            if not prompt or not stream:
                return create_api_response(
                    "Missing required form parameters: 'prompt' and 'stream'",
                    400,
                )

            if stream.lower() == "true":
                stream = True
            else:
                stream = False

            user_id = "default"
            user_email = "default"
            if self.authentication_enabled:
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    return create_api_response("No token provided", 400)

                token_id = auth_header.split("Bearer ")[1]

                # authenticate by the token
                resp, status_code = get_user_info(self.authentication_server, token_id)
                log.debug(f"Authentication response code: {status_code}")
                if status_code != 200:
                    return create_api_response(
                        "Authentication failed.",
                        status_code,
                    )
                log.debug("Successfully logged in.")

                user_id = resp["user_id"]
                user_email = resp["email"]

            # optional payload parameters
            files = request.files.getlist("files")

            file_details = []
            for file in files:
                if file.filename == "":
                    continue

                filename = secure_filename(file.filename)
                content = file.read()
                mime_type = file.mimetype

                size = len(content)
                file_details.append(
                    {
                        "name": filename,
                        "content": content,
                        "mime_type": mime_type,
                        "size": size,
                    }
                )

            # create a queue to store the response
            response_queue = Queue()
            server_input_id = str(uuid4())
            self.kv_store_set(
                f"server_input:{server_input_id}:response_queue", response_queue
            )

            # encode request in an event
            event = {
                "text": prompt,
                "user_id": user_id,
                "user_email": user_email,
                "stream": stream,
                "files": file_details,
                "timestamp": time.time(),
                "session_id": session_id,
            }

            # send the event to the cognitive mesh
            self.handle_event(server_input_id, event)

            # listen to the response queue and return the response
            if stream:
                return Response(
                    self.generate_stream_response(
                        server_input_id, event, response_queue
                    ),
                    content_type="text/event-stream",
                )
            else:
                return self.generate_simple_response(server_input_id, response_queue)

    def handle_event(self, server_input_id: int, event: Dict[str, Any]) -> None:
        payload = {
            "text": event.get("text", ""),
            "user_id": event.get("user_id", ""),
            "user_email": event.get("user_email"),
            "timestamp": event.get("timestamp", ""),
            "files": event.get("files"),
        }
        # generate session ID if not provided
        session_id = event.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
        user_properties = {
            "server_input_id": server_input_id,
            "user_id": event.get("user_id"),
            "user_email": event.get("user_email"),
            "session_id": session_id,
            "timestamp": event.get("timestamp"),
            "input_type": "rest_api",
            "use_history": False,
        }

        message = Message(payload=payload, user_properties=user_properties)
        message.set_previous(payload)
        event = Event(EventType.MESSAGE, message)
        self.process_event_with_tracing(event)
        log.debug(f"Sent event to cognitive mesh: {event}.")

    def generate_stream_response(
        self, server_input_id: int, event: Dict[str, Any], response_queue: Queue
    ) -> Generator[str, None, None]:
        while not self.stop_signal.is_set():
            try:
                response = response_queue.get(timeout=1)
            except Empty:
                continue

            chunk = {
                "id": f"restcomp-{server_input_id}",
                "session_id": response.get("session_id"),
                "created": int(time.time()),
                "content": response.get("text", ""),
                "status_message": response.get("status_message", None),
            }
            
            files = response.get("files", [])
            if files:
                chunk["files"] = files

            log.debug(f"Getting chunk: {chunk}")
            yield f"data: {json.dumps(chunk)}\n\n"

            if response.get("response_complete"):
                break
            
        yield "data: [DONE]\n\n"

    def generate_simple_response(
        self, server_input_id: int, response_queue: Queue
    ) -> Response:
        # TODO: add a timeout to the response queue
        files = []
        full_response = {"content": "", "files": []}
        while not self.stop_signal.is_set():
            try:
                response = response_queue.get(timeout=1)
            except Empty:
                continue

            log.debug(f"Getting response: {response}")
            files = response.get("files", [])
            if files and not full_response["files"]:
                full_response["files"] = files

            if response.get("text"):
                full_response["content"] += response["text"]

            if response.get("response_complete"):
                break

        user_response = {
            "id": f"restapi-{server_input_id}",
            "session_id": response.get("session_id"),
            "created": int(time.time()),
            "response": full_response,
        }

        return create_api_response(user_response, 200)
