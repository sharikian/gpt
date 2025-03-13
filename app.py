# pip install asgiref uvicorn
from flask import Flask, Response, request, stream_with_context, jsonify
from flask_cors import CORS
from g4f import ChatCompletion, models
from json import dumps
import time
from uuid import uuid4
from shutil import rmtree
from os import path
import atexit
# from asgiref.wsgi import WsgiToAsgi

app = Flask(__name__)
CORS(app)

# Cleanup function for cookies directory
@atexit.register
def remove_cookie():
    if path.exists(cookie := 'har_and_cookies'):
        rmtree(cookie)

# Define the /chat/completions endpoint
@app.route('/chat/completions', methods=['POST'])
def get_request():
    # Parse the incoming JSON request
    jsong = request.json
    messages = jsong.get('messages', [])  # List of message objects
    model = jsong.get('model', 'claude-3-5-sonnet-20241022')  # Default model name
    stream = jsong.get('stream', False)  # Streaming option

    # Handle system message if provided (OpenAI-style)
    if 'system' in jsong:
        messages.insert(0, {
            "role": "system",
            "content": jsong['system']
        })

    # Return streamed or full response based on 'stream' flag
    if stream:
        return Response(stream_with_context(generate_stream(messages)), mimetype='text/event-stream')
    else:
        return jsonify(generate_full_response(messages))

# Generate streamed response (mimics OpenAI's streaming format)
def generate_stream(messages):
    response = ChatCompletion.create(
        model=models.claude_3_5_sonnet,  # Your original Claude model
        messages=messages,
        stream=True,
    )
    for chunk in response:
        # Format each chunk as an SSE event matching OpenAI's structure
        yield f"data: {dumps({'choices': [{'delta': {'content': chunk}}]})}\n\n"
    # Signal the end of the stream
    yield "data: [DONE]\n\n"

# Generate full (non-streamed) response (mimics OpenAI's JSON format)
def generate_full_response(messages):
    response = ChatCompletion.create(
        model=models.claude_3_5_sonnet,  # Your original Claude model
        messages=messages,
        stream=False,
    )
    # Return a response object matching OpenAI's structure
    return {
        "id": f"chatcmpl-{uuid4().hex}",  # Unique ID
        "object": "chat.completion",
        "created": int(time.time()),  # Unix timestamp
        "model": "claude-3-5-sonnet-20241022",  # Model name in response
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response
            },
            "finish_reason": "stop"  # Reason for completion
        }],
        "usage": {
            "prompt_tokens": 25,  # Placeholder (adjust as needed)
            "completion_tokens": 15,  # Placeholder (adjust as needed)
            "total_tokens": 40  # Placeholder (adjust as needed)
        }
    }

@app.route('/models')
def show_modesl():
    return {
        "object": "list",
        "data": [
            {
            "id": "gpt-4.5-preview",
            "object": "model",
            "created": 1740623059,
            "owned_by": "system"
            },
            {
            "id": "gpt-4.5-preview-2025-02-27",
            "object": "model",
            "created": 1740623304,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-mini-2024-07-18",
            "object": "model",
            "created": 1721172717,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-mini-audio-preview-2024-12-17",
            "object": "model",
            "created": 1734115920,
            "owned_by": "system"
            },
            {
            "id": "dall-e-3",
            "object": "model",
            "created": 1698785189,
            "owned_by": "system"
            },
            {
            "id": "dall-e-2",
            "object": "model",
            "created": 1698798177,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-audio-preview-2024-10-01",
            "object": "model",
            "created": 1727389042,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-audio-preview",
            "object": "model",
            "created": 1727460443,
            "owned_by": "system"
            },
            {
            "id": "o1-mini-2024-09-12",
            "object": "model",
            "created": 1725648979,
            "owned_by": "system"
            },
            {
            "id": "o1-mini",
            "object": "model",
            "created": 1725649008,
            "owned_by": "system"
            },
            {
            "id": "omni-moderation-latest",
            "object": "model",
            "created": 1731689265,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-mini-audio-preview",
            "object": "model",
            "created": 1734387424,
            "owned_by": "system"
            },
            {
            "id": "omni-moderation-2024-09-26",
            "object": "model",
            "created": 1732734466,
            "owned_by": "system"
            },
            {
            "id": "babbage-002",
            "object": "model",
            "created": 1692634615,
            "owned_by": "system"
            },
            {
            "id": "tts-1-hd-1106",
            "object": "model",
            "created": 1699053533,
            "owned_by": "system"
            },
            {
            "id": "text-embedding-3-large",
            "object": "model",
            "created": 1705953180,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-2024-05-13",
            "object": "model",
            "created": 1715368132,
            "owned_by": "system"
            },
            {
            "id": "tts-1-hd",
            "object": "model",
            "created": 1699046015,
            "owned_by": "system"
            },
            {
            "id": "o1-preview",
            "object": "model",
            "created": 1725648897,
            "owned_by": "system"
            },
            {
            "id": "o1-preview-2024-09-12",
            "object": "model",
            "created": 1725648865,
            "owned_by": "system"
            },
            {
            "id": "gpt-3.5-turbo-instruct-0914",
            "object": "model",
            "created": 1694122472,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-mini-search-preview",
            "object": "model",
            "created": 1741391161,
            "owned_by": "system"
            },
            {
            "id": "tts-1-1106",
            "object": "model",
            "created": 1699053241,
            "owned_by": "system"
            },
            {
            "id": "davinci-002",
            "object": "model",
            "created": 1692634301,
            "owned_by": "system"
            },
            {
            "id": "gpt-3.5-turbo-1106",
            "object": "model",
            "created": 1698959748,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-search-preview",
            "object": "model",
            "created": 1741388720,
            "owned_by": "system"
            },
            {
            "id": "gpt-3.5-turbo-instruct",
            "object": "model",
            "created": 1692901427,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-mini-search-preview-2025-03-11",
            "object": "model",
            "created": 1741390858,
            "owned_by": "system"
            },
            {
            "id": "gpt-3.5-turbo-0125",
            "object": "model",
            "created": 1706048358,
            "owned_by": "system"
            },
            {
            "id": "gpt-4o-2024-08-06",
            "object": "model",
            "created": 1722814719,
            "owned_by": "system"
            },
            {
            "id": "gpt-3.5-turbo",
            "object": "model",
            "created": 1677610602,
            "owned_by": "openai"
            },
            {
            "id": "gpt-3.5-turbo-16k",
            "object": "model",
            "created": 1683758102,
            "owned_by": "openai-internal"
            },
            {
            "id": "gpt-4o",
            "object": "model",
            "created": 1715367049,
            "owned_by": "system"
            },
            {
            "id": "text-embedding-3-small",
            "object": "model",
            "created": 1705948997,
            "owned_by": "system"
            },
            {
            "id": "text-embedding-ada-002",
            "object": "model",
            "created": 1671217299,
            "owned_by": "openai-internal"
            },
            {
            "id": "gpt-4o-mini",
            "object": "model",
            "created": 1721172741,
            "owned_by": "system"
            },
            {
            "id": "whisper-1",
            "object": "model",
            "created": 1677532384,
            "owned_by": "openai-internal"
            },
            {
            "id": "gpt-4o-search-preview-2025-03-11",
            "object": "model",
            "created": 1741388170,
            "owned_by": "system"
            },
            {
            "id": "tts-1",
            "object": "model",
            "created": 1681940951,
            "owned_by": "openai-internal"
            },
            {
            "id": "gpt-4o-2024-11-20",
            "object": "model",
            "created": 1739331543,
            "owned_by": "system"
            }
        ]
        }

if __name__ == '__main__':
   app.run(port=9889, debug=True)

# asgi = WsgiToAsgi(app)

# uvicorn app:asgi_app --host 0.0.0.0 --port 5000
