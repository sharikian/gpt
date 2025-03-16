# pip install asgiref uvicorn flask flask-cors g4f
from flask import Flask, Response, request, stream_with_context, jsonify
from flask_cors import CORS
from g4f import ChatCompletion, models, Provider
from g4f.Provider.base_provider import BaseProvider
from json import dumps
import time
from uuid import uuid4
from shutil import rmtree
from os import path
import atexit
from asgiref.wsgi import WsgiToAsgi
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

# Configure providers
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
        
        # Try current provider first if available
        if self.current_provider:
            last_fail_time = self.last_failure.get(self.current_provider.__name__, 0)
            if current_time - last_fail_time > self.retry_delay:
                return self.current_provider
            self.current_provider = None
            
        # Find a working provider
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

# Define the /chat/completions endpoint
@app.route('/chat/completions', methods=['POST'])
def get_request():
    try:
        jsong = request.json
        messages = jsong.get('messages', [])
        model = jsong.get('model', 'gpt-4')
        stream = jsong.get('stream', False)

        if 'system' in jsong:
            messages.insert(0, {"role": "system", "content": jsong['system']})

        if stream:
            return Response(stream_with_context(generate_stream(messages)), 
                          mimetype='text/event-stream')
        else:
            return jsonify(generate_full_response(messages))
    
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def generate_stream(messages):
    retries = 3
    for attempt in range(retries):
        provider = auto_provider.get_provider()
        try:
            logger.info(f"Trying provider: {provider.__name__}")
            
            response = ChatCompletion.create(
                model=models.gpt_4o,
                messages=messages,
                stream=True,
                provider=provider,
                timeout=30
            )
            
            for chunk in response:
                content = getattr(chunk, 'content', str(chunk))
                yield f"data: {dumps({'choices': [{'delta': {'content': content}}]})}\n\n"
            yield "data: [DONE]\n\n"
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
                raise

def generate_full_response(messages):
    retries = 3
    for attempt in range(retries):
        provider = auto_provider.get_provider()
        try:
            logger.info(f"Trying provider: {provider.__name__}")
            
            response = ChatCompletion.create(
                model=models.gpt_4o,
                messages=messages,
                stream=False,
                provider=provider,
                timeout=30
            )
            
            content = getattr(response, 'content', str(response))
            return {
                "id": f"chatcmpl-{uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "gpt-4",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 25, "completion_tokens": 15, "total_tokens": 40}
            }
            
        except Exception as e:
            logger.warning(f"Provider {provider.__name__} failed: {str(e)}")
            auto_provider.mark_failed(provider)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


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



asgi = WsgiToAsgi(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
# uvicorn app:asgi_app --host 0.0.0.0 --port 5000
