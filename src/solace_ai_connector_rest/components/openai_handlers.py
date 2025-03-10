import time
import json
import uuid
from queue import Queue, Empty
from typing import Any, Dict, Generator
from flask import request, Response, jsonify
from ratelimit import limits, sleep_and_retry
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.common.log import log


def register_openai_routes(app, component, rate_limit, rate_limit_time_period):
    """Register OpenAI-compatible routes on the given Flask app."""
    
    @app.route("/v1/chat/completions", methods=["POST"])
    @app.route("/chat/completions", methods=["POST"])
    @sleep_and_retry
    @limits(rate_limit, rate_limit_time_period)
    def openai_request_handler():
        server_input_id = str(uuid.uuid4())
        event = request.json

        response_queue = Queue()
        component.kv_store_set(
            f"server_input:{server_input_id}:response_queue", response_queue
        )

        handle_event_openai(component, server_input_id, event)

        if event.get("stream", False):
            return Response(
                generate_stream_response_openai(
                    component, server_input_id, event, response_queue
                ),
                content_type="text/event-stream",
            )
        else:
            return generate_simple_response_openai(
                component, server_input_id, event, response_queue
            )


def handle_event_openai(component, server_input_id, event):
    """Process an OpenAI-compatible event."""
    messages = event.get("messages", [])
    combined_message = "Input messages that arrived through an OpenAI-compatible server interface:\n"
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        combined_message += f"{role}: {content}\n"

    # generate session ID if not provided
    session_id = event.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())

    payload = {
        "text": combined_message.strip(),
        "user_id": event.get("user", "default@example.com"),
        "user_email": event.get("user", "default@example.com"),
        "timestamp": str(int(time.time())),
        "files": []
    }
    user_properties = {
        "server_input_id": server_input_id,
        "user_id": event.get("user", ""),
        "user_email": event.get("user", "default@example.com"),
        "timestamp": str(int(time.time())),
        "input_type": "openai_server",
        "use_history": False,
        "session_id": session_id,
    }

    message = Message(payload=payload, user_properties=user_properties)
    message.set_previous(payload)
    event = Event(EventType.MESSAGE, message)
    component.process_event_with_tracing(event)

    return "Message received"


def generate_stream_response_openai(component, server_input_id, event, response_queue):
    """Generate a streaming response for OpenAI-compatible requests."""
    model = event.get("model", "solace-agent-mesh")
    while not component.stop_signal.is_set():
        try:
            response = response_queue.get(timeout=1)
        except Empty:
            continue

        chunk = {
            "id": f"chatcmpl-{server_input_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": response.get("text", "")},
                    "finish_reason": (
                        "stop" if response.get("response_complete") else None
                    ),
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"

        if response.get("response_complete"):
            break

    yield "data: [DONE]\n\n"


def generate_simple_response_openai(component, server_input_id, event, response_queue):
    """Generate a simple (non-streaming) response for OpenAI-compatible requests."""
    model = event.get("model", "solace-agent-mesh")
    full_response = ""
    while not component.stop_signal.is_set():
        try:
            response = response_queue.get(timeout=1)
        except Empty:
            continue

        if response.get("text"):
            full_response += response["text"]

        if response.get("response_complete"):
            break

    response = {
        "id": f"chatcmpl-{server_input_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": full_response},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(
                " ".join(
                    msg["content"] for msg in event.get("messages", [])
                ).split()
            ),
            "completion_tokens": len(full_response.split()),
            "total_tokens": len(
                " ".join(
                    msg["content"] for msg in event.get("messages", [])
                ).split()
            )
            + len(full_response.split()),
        },
    }

    return jsonify(response)
