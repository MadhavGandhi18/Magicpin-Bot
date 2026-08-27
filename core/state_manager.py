from typing import Dict, Any, Optional

class StateManager:
    def __init__(self):
        # contexts[scope][context_id] = {"version": int, "payload": dict}
        self.contexts: Dict[str, Dict[str, Dict[str, Any]]] = {
            "category": {},
            "merchant": {},
            "customer": {},
            "trigger": {}
        }
        
        # conversations[conversation_id] = list of message dicts
        self.conversations: Dict[str, list] = {}
        # conversation_states[conversation_id] = str (e.g., "active", "suppressed")
        self.conversation_states: Dict[str, str] = {}

    def get_context_count(self) -> Dict[str, int]:
        return {scope: len(self.contexts[scope]) for scope in self.contexts}

    def update_context(self, scope: str, context_id: str, version: int, payload: Dict[str, Any]) -> tuple[bool, str, Optional[int]]:
        """Returns (accepted, reason_or_ack, current_version)"""
        if scope not in self.contexts:
            return False, "invalid_scope", None
            
        current = self.contexts[scope].get(context_id)
        if current and current["version"] >= version:
            return False, "stale_version", current["version"]
            
        self.contexts[scope][context_id] = {
            "version": version,
            "payload": payload
        }
        return True, f"ack_{context_id}_v{version}", None

    def get_context(self, scope: str, context_id: str) -> Optional[Dict[str, Any]]:
        if scope in self.contexts and context_id in self.contexts[scope]:
            return self.contexts[scope][context_id]["payload"]
        return None

    def append_message(self, conversation_id: str, from_role: str, message: str) -> None:
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append({"from": from_role, "msg": message})

    def get_conversation_history(self, conversation_id: str) -> list:
        return self.conversations.get(conversation_id, [])
        
    def set_conversation_state(self, conversation_id: str, state: str):
        self.conversation_states[conversation_id] = state
        
    def get_conversation_state(self, conversation_id: str) -> str:
        return self.conversation_states.get(conversation_id, "active")

state_manager = StateManager()
