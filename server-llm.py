from flask import Flask, Response, request, stream_with_context, jsonify
from flask_cors import CORS
from g4f import ChatCompletion, models, Provider
from g4f.Provider.base_provider import BaseProvider
from json import dumps
from uuid import uuid4
from shutil import rmtree
from os import path
import atexit
import time
import logging
from typing import List

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cleanup function for cookies directory
@atexit.register
def remove_cookie():
    if path.exists(cookie := 'har_and_cookies'):
        rmtree(cookie)

# Define active providers that support Anthropic models
# Note: Replace with actual g4f providers supporting Anthropic models
ACTIVE_PROVIDERS = [
    Provider.Copilot,
    Provider.Yqcloud,
    Provider.ChatGptEs,
    Provider.PollinationsAI,
    Provider.Glider,
    Provider.Liaobots,
    Provider.Phind,
]

class AutoProvider:
    def __init__(self, providers: List[BaseProvider]):
        self.providers = providers
        self.current_provider = None
        self.last_failure = {}
        self.retry_delay = 300  # 5 minutes in seconds

    def get_provider(self):
        current_time = time.time()
        if self.current_provider:
            last_fail_time = self.last_failure.get(self.current_provider.__name__, 0)
            if current_time - last_fail_time > self.retry_delay:
                return self.current_provider
            self.current_provider = None
        for provider in self.providers:
            last_fail_time = self.last_failure.get(provider.__name__, 0)
            if current_time - last_fail_time > self.retry_delay:
                self.current_provider = provider
                return provider
        raise Exception("All providers are temporarily unavailable")

    def mark_failed(self, provider: BaseProvider):
        self.last_failure[provider.__name__] = time.time()
        self.current_provider = None

auto_provider = AutoProvider(ACTIVE_PROVIDERS)

# Endpoint for direct translation (non-streaming)
@app.route('/v1/direct', methods=['POST'])
def direct_translate():
    jsong = request.json
    messages = jsong['messages']
    system_message = jsong.get('system', '')

    messages.insert(0, {
        "role": "user",
        "content": system_message
    })

    retries = 3
    for attempt in range(retries):
        provider = auto_provider.get_provider()
        try:
            logger.info(f"Trying provider: {provider.__name__}")
            response = ChatCompletion.create(
                #model=models.gpt_4, #models.claude_3_5_sonnet,
                messages=messages,
                provider=provider,
                timeout=30
            )
            full_response = ''.join([message for message in response])
            return jsonify({"translatedText": full_response})
        except Exception as e:
            logger.warning(f"Provider {provider.__name__} failed: {str(e)}")
            auto_provider.mark_failed(provider)
            if attempt < retries - 1:
                delay = 2 ** attempt
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(f"Direct translation failed after {retries} attempts: {str(e)}")
                return jsonify({"error": "All providers failed"}), 500

# Endpoint for streaming messages
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
        retries = 3
        for attempt in range(retries):
            provider = auto_provider.get_provider()
            try:
                logger.info(f"Trying provider: {provider.__name__}")
                response = ChatCompletion.create(
                    #model=models.gpt_4,
                    messages=messages,
                    stream=True,
                    provider=provider,
                    timeout=30
                )
                # Event: message_start
                yield f"event: message_start\ndata: {dumps({'type': 'message_start', 'message': {'id': f'msg_{uuid4().hex}', 'type': 'message', 'role': 'assistant', 'content': [], 'model': 'claude-3-5-sonnet-20241022', 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 25, 'output_tokens': 1}}})}\n\n".encode('utf-8')
                # Event: content_block_start
                yield f"event: content_block_start\ndata: {dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n".encode('utf-8')
                # Event: ping
                yield f"event: ping\ndata: {dumps({'type': 'ping'})}\n\n".encode('utf-8')
                for message in response:
                    yield f"event: content_block_delta\ndata: {dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': message}})}\n\n".encode('utf-8')
                # Event: content_block_stop
                yield f"event: content_block_stop\ndata: {dumps({'type': 'content_block_stop', 'index': 0})}\n\n".encode('utf-8')
                # Event: message_delta
                yield f"event: message_delta\ndata: {dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': 15}})}\n\n".encode('utf-8')
                # Event: message_stop
                yield f"event: message_stop\ndata: {dumps({'type': 'message_stop'})}\n\n".encode('utf-8')
                return
            except Exception as e:
                logger.warning(f"Provider {provider.__name__} failed: {str(e)}")
                auto_provider.mark_failed(provider)
                if attempt < retries - 1:
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    yield f"data: {dumps({'error': 'All providers failed'})}\n\n"
                    yield "data: [DONE]\n\n"
                    logger.error(f"Streaming failed after {retries} attempts: {str(e)}")
                    break

    return Response(stream(), mimetype='text/event-stream')

# Endpoint to list available models
@app.route('/models')
def show_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "claude-3-5-sonnet-20241022",
                "object": "model",
                "created": 1699053533,
                "owned_by": "anthropic"
            }
            # Add other Anthropic models supported by g4f as needed
        ]
    }

if __name__ == '__main__':
    app.run(port=5000, debug=True)
