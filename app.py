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
import threading

# Initialize Flask app
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

# Global cache for models: [{"name": "gpt-4", "state": "enable|disable|checking", "rate": response_time}]
MODELS_TO_CHECK = []

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

def extract_models_from_providers():
    """Extract unique models from all active providers."""
    all_models = set()
    for provider in ACTIVE_PROVIDERS:
        try:
            if hasattr(provider, 'models'):
                provider_models = provider.models
            elif hasattr(provider, 'get_models'):
                provider_models = provider.get_models()
            else:
                provider_models = ["gpt-4", "gpt-3.5-turbo", "gpt-4o"]
            all_models.update(provider_models)
        except Exception as e:
            logger.warning(f"Failed to extract models from {provider.__name__}: {str(e)}")
    return list(all_models)

def is_model_active(model: str):
    """Test if a model is active. Returns (is_active, response_time)."""
    messages = [{"role": "user", "content": "Hello"}]
    retries = len(ACTIVE_PROVIDERS)
    for attempt in range(retries):
        provider = auto_provider.get_provider()
        start_time = time.time()
        try:
            response = ChatCompletion.create(
                model=model,
                messages=messages,
                stream=False,
                provider=provider,
                timeout=10  # Short timeout for testing
            )
            content = getattr(response, 'content', str(response))
            if content.strip():
                response_time = time.time() - start_time
                return True, response_time
        except Exception as e:
            logger.debug(f"Model {model} failed with provider {provider.__name__}: {str(e)}")
            auto_provider.mark_failed(provider)
            continue
    return False, None

def update_active_models_cache():
    """Update model states and response times in the background."""
    def background_check():
        for model in MODELS_TO_CHECK:
            model["state"] = "checking"  # Reset to checking during update
        for model in MODELS_TO_CHECK:
            active, response_time = is_model_active(model["name"])
            model["state"] = "enable" if active else "disable"
            model["rate"] = response_time if active else None
    threading.Thread(target=background_check).start()

def schedule_cache_update():
    """Schedule cache updates every 1 hour."""
    update_active_models_cache()
    threading.Timer(3600, schedule_cache_update).start()

def initialize_cache():
    """Initialize the model cache with all models set to 'checking'."""
    global MODELS_TO_CHECK
    extracted_models = extract_models_from_providers()
    MODELS_TO_CHECK = [{"name": model, "state": "checking", "rate": None} for model in extracted_models]
    schedule_cache_update()  # Start periodic background updates

# Initialize cache when the app starts
initialize_cache()

def get_active_model_fallback(original_model: str):
    """Find an active model to fall back to if the original model fails."""
    for model in MODELS_TO_CHECK:
        if model["state"] == "enable" and model["name"] != original_model:
            return model["name"]
    return None

# Define the /chat/completions endpoint
@app.route('/chat/completions', methods=['POST'])
def get_request():
    try:
        jsong = request.json
        messages = jsong.get('messages', [])
        model = jsong.get('model', 'gpt-4')  # Default to gpt-4 if not specified
        stream = jsong.get('stream', False)

        if 'system' in jsong:
            messages.insert(0, {"role": "system", "content": jsong['system']})

        # Try the requested model first
        model_info = next((m for m in MODELS_TO_CHECK if m["name"] == model), None)
        if model_info and model_info["state"] == "enable":
            if stream:
                response = generate_stream(model, messages)
            else:
                response = generate_full_response(model, messages)
            if response:  # Check if response is valid
                return response if stream else jsonify(response)

        # If the model fails or isn’t enabled, fall back to an active model
        logger.warning(f"Model {model} failed or not enabled, attempting fallback.")
        fallback_model = get_active_model_fallback(model)
        if not fallback_model:
            return jsonify({"error": "No active models available."}), 503

        logger.info(f"Switching to fallback model: {fallback_model}")
        if stream:
            return Response(stream_with_context(generate_stream(fallback_model, messages)), 
                            mimetype='text/event-stream')
        else:
            response = generate_full_response(fallback_model, messages)
            response["model"] = fallback_model  # Update response to reflect the used model
            return jsonify(response)

    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def generate_stream(model, messages):
    retries = len(ACTIVE_PROVIDERS)
    for attempt in range(retries):
        provider = auto_provider.get_provider()
        try:
            logger.info(f"Streaming with provider: {provider.__name__} and model: {model}")
            response = ChatCompletion.create(
                model=model,
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
            if attempt == retries - 1:
                return None  # Indicate failure to trigger fallback
            continue

def generate_full_response(model, messages):
    retries = len(ACTIVE_PROVIDERS)
    for attempt in range(retries):
        provider = auto_provider.get_provider()
        try:
            logger.info(f"Using provider: {provider.__name__} and model: {model}")
            response = ChatCompletion.create(
                model=model,
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
                "model": model,
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
            if attempt == retries - 1:
                return None  # Indicate failure to trigger fallback
            time.sleep(2 ** attempt)

@app.route('/models')
def show_models():
    """Return the list of models with their current states and rates."""
    return jsonify({"models": MODELS_TO_CHECK})

# Convert Flask app to ASGI
asgi = WsgiToAsgi(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)