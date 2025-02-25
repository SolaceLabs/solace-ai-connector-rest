# RestOutput

Rest output component that processes cognitive mesh responses and prepares them for REST API delivery. The component handles both streaming and non-streaming responses, manages file attachments, and supports status updates. Responses are sent through a cached output_queue back to rest_input.py for delivery to the client.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: rest_output
component_config:
  rest_output:
    reponse_complete_on_last_chunk: <boolean>  # Set response_complete flag on last chunk (default: false)
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| reponse_complete_on_last_chunk | False | false | When true, sets response_complete flag on the last chunk of a streaming response |

## Component Input Schema

```json
{
  "message_info": {
    "type": "<string>",                 # Message type identifier
    "user_email": "<string>",           # User's email address
    "client_msg_id": "<string>",        # Client-provided message ID
    "user_id": "<string>",              # User identifier
    "session_id": "<string>",           # Session identifier
    "server_input_id": "<string>",      # Server input identifier
    "files": [                          # Optional file attachments
      {
        "name": "<string>",             # File name
        "content": "<string>",          # File content
        "mime_type": "<string>",        # MIME type
        "filetype": "<string>",         # File type
        "size": "<number>"              # File size in bytes
      }
    ]
  },
  "content": {
    "text": "<string>",                 # Response text content
    "chunk": "<string>",                # Chunk of streaming response
    "uuid": "<string>",                 # Response UUID
    "streaming": "<boolean>",           # Streaming response flag
    "response_complete": "<boolean>",    # Response complete flag
    "first_chunk": "<boolean>",         # First chunk flag
    "last_chunk": "<boolean>",          # Last chunk flag
    "status_update": "<boolean>"        # Status update flag
  }
}
```

| Field | Required | Description |
| --- | --- | --- |
| message_info | True | Container for message metadata |
| message_info.type | False | Type of message |
| message_info.user_email | False | Email of the user |
| message_info.client_msg_id | False | Client-provided message identifier |
| message_info.user_id | False | User identifier |
| message_info.session_id | True | Session identifier for the conversation |
| message_info.server_input_id | True | Server input identifier for response routing |
| message_info.files | False | Array of file attachments |
| content | True | Container for response content |
| content.text | False | Main response text |
| content.chunk | False | Chunk of text for streaming responses |
| content.uuid | False | Unique identifier for the response |
| content.streaming | False | Indicates if response is streaming |
| content.response_complete | False | Indicates if response is complete |
| content.first_chunk | False | Indicates first chunk of stream |
| content.last_chunk | False | Indicates last chunk of stream |
| content.status_update | False | Indicates a status update message |

## Component Behavior

The component processes cognitive mesh responses in the following ways:

1. **Streaming Responses**
   - Breaks response into chunks
   - Marks first and last chunks
   - Supports status updates during streaming
   - Manages streaming state with timeouts

2. **File Handling**
   - Processes file attachments
   - Includes file metadata in response
   - Supports multiple files per response

3. **Response Completion**
   - Sets response_complete flag based on configuration
   - Supports explicit completion marking
   - Handles streaming completion states

4. **State Management**
   - Maintains streaming state
   - Ages out old streaming states
   - Handles session tracking

5. **Queue Management**
   - Uses cached output queues
   - Handles queue routing via server_input_id
   - Supports queue cleanup
