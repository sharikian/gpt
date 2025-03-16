from flask import Flask, Response, request, stream_with_context, jsonify
from flask_cors import CORS
from g4f import ChatCompletion, models
from json import dumps
from uuid import uuid4
from shutil import rmtree
from os import path
import atexit

app = Flask(__name__)
CORS(app)

@atexit.register
def remove_cookie():
    if path.exists(cookie:='har_and_cookies'):
        rmtree(cookie)

@app.route('/v1/direct', methods=['POST'])
def direct_translate():
    jsong = request.json
    messages = jsong['messages']
    system_message = jsong.get('system', '')

    messages.insert(0, {
        "role": "user",
        "content": system_message
    })

    response = ChatCompletion.create(
        model=models.claude_3_5_sonnet,
        messages=messages
    )
    full_response = ''.join([message for message in response])

    return jsonify({"translatedText": full_response})

@app.route('/v1/messages', methods=['POST'])
def get_request():
    jsong = request.json
    messages = jsong['messages']
    try:
        messages.insert(0, {
            "role": "user",
            "content": jsong['system']
        })
    except KeyError:
        pass

    @stream_with_context
    def stream():
        # Event: message_start
        yield f"event: message_start\ndata: {dumps({'type': 'message_start', 'message': {'id': f'msg_{uuid4().hex}', 'type': 'message', 'role': 'assistant', 'content': [], 'model': 'claude-3-5-sonnet-20241022', 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 25, 'output_tokens': 1}}})}\n\n".encode('utf-8')
        
        # Event: content_block_start
        yield f"event: content_block_start\ndata: {dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n".encode('utf-8')

        # Event: ping
        yield f"event: ping\ndata: {dumps({'type': 'ping'})}\n\n".encode('utf-8')

        # Handle each content block delta
        response = ChatCompletion.create(
            model=models.claude_3_5_sonnet,
            messages=messages,
            stream=True,
        )
        for message in response:
            yield f"event: content_block_delta\ndata: {dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': message}})}\n\n".encode('utf-8')

        # Event: content_block_stop
        yield f"event: content_block_stop\ndata: {dumps({'type': 'content_block_stop', 'index': 0})}\n\n".encode('utf-8')

        # Event: message_delta
        yield f"event: message_delta\ndata: {dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': 15}})}\n\n".encode('utf-8')

        # Event: message_stop
        yield f"event: message_stop\ndata: {dumps({'type': 'message_stop'})}\n\n".encode('utf-8')

    return Response(stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(port=9889, debug=True)
