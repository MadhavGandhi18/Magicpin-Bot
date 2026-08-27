import json
import asyncio
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel

from config import settings
from prompts.system_base import get_system_prompt, get_action_mode_prompt
from models.api_schemas import ComposedAction, ReplyAction

gemini_client = genai.Client(api_key=settings.gemini_api_key)

def filter_digest_by_signals(digest: list, signals: list) -> list:
    """RAG-lite: Filters category digest based on keyword match with merchant signals."""
    if not digest:
        return []
    if not signals:
        return digest
        
    filtered = []
    signals_lower = [str(s).lower() for s in signals]
    
    for item in digest:
        item_lower = str(item).lower()
        if any(s in item_lower for s in signals_lower):
            filtered.append(item)
            
    return filtered if filtered else digest[:2]


class LLMClient:
    def __init__(self):
        self.model_name = settings.model_name

    async def compose_proactive(self, trigger: Dict[str, Any], merchant: Dict[str, Any], 
                                category: Dict[str, Any], customer: Optional[Dict[str, Any]]) -> Optional[ComposedAction]:
        """Generates a proactive message using the 4 contexts."""
        
        # RAG-Lite: Filter digest
        digest = category.get('digest', [])
        signals = merchant.get('signals', [])
        if digest:
            category['digest'] = filter_digest_by_signals(digest, signals)
            
        # Multi-lingual injection
        languages = merchant.get('identity', {}).get('languages', [])
        language_directive = "- Use natural Hinglish (Hindi words written in the English alphabet) mixed with English." if 'hi' in languages else ""
        
        system_instruction = get_system_prompt(trigger.get('kind', ''), category.get('voice', {}), language_directive)
        
        context_payload = {
            "Trigger": trigger,
            "Merchant": merchant,
            "Category": category,
            "Customer": customer if customer else "None (merchant-facing)"
        }
        
        prompt = f"Compose the next message based on the following contexts:\n\n{json.dumps(context_payload, indent=2)}\n\nMUST return a valid JSON object matching this schema: {{'conversation_id': 'string', 'merchant_id': 'string', 'send_as': 'string', 'body': 'string', 'cta': 'string', 'rationale': 'string'}}"
        
        try:
            # Attempt 1: Nemotron via OpenRouter
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }
            
            def fetch_nemotron_proactive():
                import urllib.request
                import time
                for attempt in range(5):
                    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
                    try:
                        with urllib.request.urlopen(req) as response:
                            res = json.loads(response.read().decode())
                            if "error" in res:
                                time.sleep(2)
                                continue
                            if "choices" in res and res["choices"]:
                                return res["choices"][0]["message"]["content"]
                    except urllib.error.HTTPError as e:
                        if e.code in [502, 503]:
                            time.sleep(2)
                            continue
                        raise e
                return None
                
            content = await asyncio.to_thread(fetch_nemotron_proactive)
            if content:
                result = ComposedAction.model_validate_json(content)
            else:
                raise Exception("Failed to get Nemotron response after 3 attempts")
            
        except Exception as e:
            print(f"Nemotron generation error (proactive): {e}. Falling back to Gemini...")
            try:
                # Attempt 2: Gemini
                response = await asyncio.to_thread(
                    gemini_client.models.generate_content,
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=ComposedAction
                    )
                )
                result = ComposedAction.model_validate_json(response.text)
            except Exception as e2:
                print(f"Gemini fallback error (proactive): {e2}")
                return None
                
        # Ensure required fields are set correctly based on context
        if not result.conversation_id:
            cust_part = f"_{customer['customer_id']}" if customer else ""
            result.conversation_id = f"conv_{merchant['merchant_id']}_{trigger['id']}{cust_part}"
        
        result.merchant_id = merchant['merchant_id']
        if customer:
            result.customer_id = customer['customer_id']
        result.trigger_id = trigger['id']
        
        return result

    async def compose_reply(self, conversation_id: str, conversation_history: list, 
                            trigger: Dict[str, Any], merchant: Dict[str, Any], 
                            category: Dict[str, Any], intent_state: str) -> ReplyAction:
        """Generates a reply based on conversation history and intent state."""
        
        if intent_state == "intent_action":
            system_instruction = get_action_mode_prompt()
        else:
            # Multi-lingual injection
            languages = merchant.get('identity', {}).get('languages', []) if merchant else []
            language_directive = "- Use natural Hinglish (Hindi words written in the English alphabet) mixed with English." if 'hi' in languages else ""
            system_instruction = get_system_prompt(trigger.get('kind', ''), category.get('voice', {}) if category else {}, language_directive)
            
        context_payload = {
            "Trigger": trigger,
            "Merchant": merchant,
            "Category": category,
            "History": conversation_history
        }
        
        prompt = f"Compose the reply action based on the history and context:\n\n{json.dumps(context_payload, indent=2)}\n\nMUST return a valid JSON object matching this schema: {{'action': 'string', 'body': 'string', 'cta': 'string', 'rationale': 'string'}}"
        
        try:
            # Attempt 1: Nemotron via OpenRouter
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }
            
            def fetch_nemotron():
                import urllib.request
                import time
                for attempt in range(5):
                    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
                    try:
                        with urllib.request.urlopen(req) as response:
                            res = json.loads(response.read().decode())
                            if "error" in res:
                                time.sleep(2)
                                continue
                            if "choices" in res and res["choices"]:
                                return res["choices"][0]["message"]["content"]
                    except urllib.error.HTTPError as e:
                        if e.code in [502, 503]:
                            time.sleep(2)
                            continue
                        raise e
                return None
                
            content = await asyncio.to_thread(fetch_nemotron)
            if content:
                result = ReplyAction.model_validate_json(content)
                return result
            else:
                raise Exception("Failed to get Nemotron response after 3 attempts")
            
        except Exception as e:
            print(f"Nemotron generation error (reply): {e}. Falling back to Gemini...")
            try:
                # Attempt 2: Gemini
                response = await asyncio.to_thread(
                    gemini_client.models.generate_content,
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=ReplyAction
                    )
                )
                result = ReplyAction.model_validate_json(response.text)
                return result
            except Exception as e2:
                print(f"Gemini fallback error (reply): {e2}")
                # Attempt 3: Hardcoded Safe Fallback
                return ReplyAction(
                    action="send",
                    body="I understand. Let me get back to you shortly.",
                    cta="open_ended",
                    rationale="Fallback reply due to LLM error."
                )

llm_client = LLMClient()
