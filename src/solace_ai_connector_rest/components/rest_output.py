import json
from datetime import datetime
from uuid import uuid4

from solace_ai_connector.common.log import log
from solace_ai_connector.components.component_base import ComponentBase


info = {
    "class_name": "RestOutput",
    "description": "This component receives REST API requests and prepare them for cognitive mesh processing.",
    "config_parameters": [
        {
            "name": "rest_output",
            "type": "boolean",
            "description": "This component handles output for a RestAPI-compatible server.",
            "default": False,
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "message_info": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                    },
                    "user_id": {
                        "type": "string",
                    },
                },
                "required": ["session_id"],
            },
            "content": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                },
            },
        },
        "required": ["message_info", "content"],
    },
}


class RestOutput(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.reponse_complete_on_last_chunk = self.get_config(
            "reponse_complete_on_last_chunk", False
        )
        self.http_server_output_id = str(uuid4())
        self.streaming_state_key = (
            f"http_server_output:{self.http_server_output_id}:streaming_state"
        )
        self.kv_store_set(self.streaming_state_key, {})

    def invoke(self, message, data):
        message_info = data.get("message_info")
        files = message_info.get("files", "")
        content = data.get("content")
        chunk = content.get("chunk")
        text = content.get("text", None)
        uuid = content.get("uuid")
        streaming = content.get("streaming", False)
        response_complete = content.get("response_complete", False)
        last_chunk = content.get("last_chunk")
        first_chunk = content.get("first_chunk")
        status_update = content.get("status_update", False)
        server_input_id = message_info.get("server_input_id")

        user_properties = message.get_user_properties()
        session_id = user_properties.get("session_id")
        if not streaming or (self.reponse_complete_on_last_chunk and last_chunk):
            response_complete = True

        response_queue = self.kv_store_get(
            f"server_input:{server_input_id}:response_queue"
        )

        if not response_queue:
            log.error("http_server_output: No response_queue specified in message")
            self.discard_current_message()
            return None

        if status_update:
            status_message = text
        else:
            status_message = None

        response_queue.put(
            {
                "text": chunk,
                "stream": streaming,
                "first_chunk": first_chunk,
                "last_chunk": last_chunk,
                "uuid": uuid,
                "session_id": session_id,
                "response_complete": response_complete,
                "files": files,
                "status_message": status_message,
            }
        )

        return data

    def get_streaming_state(self, uuid):
        streaming_state = self.kv_store_get(self.streaming_state_key)
        return streaming_state.get(uuid)

    def add_streaming_state(self, uuid):
        streaming_state = self.kv_store_get(self.streaming_state_key)
        state = {
            "create_time": datetime.now().isoformat(),
        }
        streaming_state[uuid] = state
        self.kv_store_set(self.streaming_state_key, streaming_state)
        self.age_out_streaming_state()
        return state

    def delete_streaming_state(self, uuid):
        streaming_state = self.kv_store_get(self.streaming_state_key)
        streaming_state.pop(uuid, None)
        self.kv_store_set(self.streaming_state_key, streaming_state)

    def age_out_streaming_state(self, age=60):
        streaming_state = self.kv_store_get(self.streaming_state_key)
        now = datetime.now()
        for uuid, state in list(streaming_state.items()):
            create_time = datetime.fromisoformat(state["create_time"])
            if (now - create_time).total_seconds() > age:
                del streaming_state[uuid]
        self.kv_store_set(self.streaming_state_key, streaming_state)
