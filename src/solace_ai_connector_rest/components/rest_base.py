import queue
from abc import abstractmethod
from flask import Flask
from flask_cors import CORS
from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.event import Event, EventType

info = {
    "config_parameters": [
        {
            "name": "listen_port",
            "type": "number",
            "description": "The port to listen to for incoming messages.",
            "default": 5000,
            "required": False,
        },
        {
            "name": "host",
            "type": "string",
            "description": "The host to listen to for incoming messages.",
            "default": "127.0.0.1",
            "required": False,
        }
    ],
    "output_schema": {
        "type": "object",
        "properties": {
            "event": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                    "user_id": {
                        "type": "string",
                    },
                    "timestamp": {
                        "type": "string",
                    },
                },
            },
        },
        "required": ["event"],
    },
}


class RestBase(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.input_queue = queue.Queue()
        self.host = self.get_config("host", "127.0.0.1")
        self.acknowledgement_message = None
        self.app = None
        self.init_app()

    def init_app(self):
        self.app = Flask(__name__)
        CORS(self.app)
        
        # Add health check endpoint
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return '', 200
            
        self.register_routes()

    def run(self):
        self.app.run(host=self.host, port=self.listen_port)

    def stop_component(self):
        func = self.app.config.get("werkzeug.server.shutdown")
        if func is None:
            raise RuntimeError("Not running with the Werkzeug Server")
        func()

        # Clear the input queue
        with self.input_queue.mutex:
            self.input_queue.queue.clear()

    def get_next_event(self):
        message = self.input_queue.get()
        return Event(EventType.MESSAGE, message)

    def invoke(self, _message, data):
        return data

    def handle_event(self, server_input_id, event):
        payload = {
            "text": event.get("message", ""),
            "user_id": event.get("user_id", "default@example.com"),
            "timestamp": event.get("timestamp", ""),
        }
        user_properties = {
            "server_input_id": server_input_id,
            "user_id": event.get("user_id", ""),
            "timestamp": event.get("timestamp", ""),
            "input_type": "rest_api",
            "use_history": False,
        }

        message = Message(payload=payload, user_properties=user_properties)
        message.set_previous(payload)
        event = Event(EventType.MESSAGE, message)
        self.process_event_with_tracing(event)

    @abstractmethod
    def register_routes(self):
        pass

    @abstractmethod
    def generate_stream_response(self, server_input_id, event, response_queue):
        pass

    @abstractmethod
    def generate_simple_response(self, server_input_id, event, response_queue):
        pass
