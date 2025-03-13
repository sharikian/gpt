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
from asgiref.wsgi import WsgiToAsgi

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

#if __name__ == '__main__':
#    app.run(port=9889, debug=True)

asgi = WsgiToAsgi(app)

# uvicorn app:asgi_app --host 0.0.0.0 --port 5000
