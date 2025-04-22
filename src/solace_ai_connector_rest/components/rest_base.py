import queue
from abc import abstractmethod
from flask import Flask
from flask_cors import CORS
from gevent.pywsgi import WSGIServer
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
        self.app.env = 'production'
        CORS(self.app)
        
        # Add health check endpoint
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return '', 200
            
        self.register_routes()

    def run(self):
        self.http_server = WSGIServer((self.host, self.listen_port), self.app)
        self.http_server.serve_forever()

    def stop_component(self):
        if hasattr(self, 'http_server') and self.http_server.started:
            try:
                self.http_server.stop(timeout=10)
            except Exception as e:
                print("Error stopping WebSocket server: %s", str(e))

        # Clear the input queue
        if hasattr(self, 'input_queue') and self.input_queue is not None:
            try:
                with self.input_queue.mutex:
                    self.input_queue.queue.clear()
            except Exception as e:
                print(f"Error clearing input queue: {e}")

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
