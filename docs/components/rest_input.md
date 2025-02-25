# RestInput

Rest input component that receives REST API requests and prepares them for cognitive mesh processing. When a message is sent by the user, the RestReceiver class picks it up in the register_handler function using `@app.route()` from flask. The message is then sent to the broker to be processed by the chatbot. Then rest_input.py awaits for a response on a cached output queue. When it receives a response, it calls a function to return the message back to the user. This process continues until a response_complete flag is set to True.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: rest_input
component_config:
  rest_input:
    authentication:
      enabled: <boolean>        # Enable/disable authentication
      server: <string>          # Authentication server URL (required if auth enabled)
    host: <string>             # Host address (default: 127.0.0.1)
    endpoint: <string>         # API endpoint path (e.g. /api/v1/request)
    rate_limit: <number>       # Max requests per minute (default: 100)
  listen_port: <number>        # Port to listen on (default: 5050)
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| authentication.enabled | True | false | Enable/disable authentication |
| authentication.server | False | - | Authentication server URL (required if auth enabled) |
| host | True | 127.0.0.1 | Host address to bind to |
| endpoint | True | /api/v1/request | API endpoint path |
| rate_limit | False | 100 | Maximum number of requests per minute |
| listen_port | False | 5050 | Port to listen on |

## REST Endpoints

### POST {endpoint}

Main endpoint for submitting requests to the cognitive mesh.

#### Request Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| prompt | string | Yes | The input text/prompt to process |
| stream | boolean | Yes | Whether to stream the response |
| session_id | string | No | Session identifier for the conversation |
| files | file[] | No | Array of files to upload |

#### Headers

| Header | Required | Description |
| --- | --- | --- |
| Authorization | If auth enabled | Bearer token for authentication |

#### Response Format

For non-streaming responses:
```json
{
  "id": "restapi-{uuid}",
  "session_id": "{session_id}",
  "created": 1234567890,
  "response": {
    "content": "Response text",
    "files": []
  }
}
```

For streaming responses:

```
data: {"id":"restcomp-{uuid}","session_id":"{session_id}","created":1234567890,"content":null, status_message: "Getting result..."}

data: {"id":"restcomp-{uuid}","session_id":"{session_id}","created":1234567890,"content":"Created file", status_message:null}

files: [{"name":"file1.txt", "content": "abcdefgABCDEFG"}]

data: [DONE]
```

### GET /health

Health check endpoint that returns 200 OK when service is healthy.



## Component Output Schema

```
{
  event:   {
    text:     <string>,
    files: [
      {
        name:         <string>,
        content:         <string>,
        mime_type:         <string>,
        filetype:         <string>,
        size:         <number>
      },
      ...
    ],
    user_email:     <string>,
    mentions: [
      <string>,
      ...
    ],
    type:     <string>,
    user_id:     <string>,
    client_msg_id:     <string>
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| event | True |  |
| event.text | False |  |
| event.files | False |  |
| event.files[].name | False |  |
| event.files[].content | False |  |
| event.files[].mime_type | False |  |
| event.files[].filetype | False |  |
| event.files[].size | False |  |
| event.user_email | False |  |
| event.mentions | False |  |
| event.type | False |  |
| event.user_id | False |  |
| event.client_msg_id | False |  |
