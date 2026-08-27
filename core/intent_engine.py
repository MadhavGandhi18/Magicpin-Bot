from collections import defaultdict
import re

class IntentEngine:
    def __init__(self):
        # Words indicating hostility
        self.hostile_words = {"stop", "spam", "annoying", "useless", "bothering", "unsubscribe", "don't message", "leave me alone"}
        # Words indicating intent transition / agreement
        self.intent_words = {"let's do it", "go ahead", "sure", "yes please", "do it", "draft it", "ok lets do it", "confirm"}
        # Words indicating busy state
        self.busy_words = {"busy", "later", "not right now", "not now", "another time", "call me back"}
        
        # Track messages per merchant to detect auto-replies across conversation IDs
        self.merchant_history = defaultdict(list)
        
    def detect_intent(self, merchant_id: str, conversation_id: str, latest_msg: str) -> str:
        """Returns intent: 'auto_reply_hell', 'hostile', 'busy', 'intent_action', or 'neutral'"""
        clean_msg = latest_msg.strip().lower()
        if not clean_msg:
            return "neutral"
            
        if merchant_id:
            self.merchant_history[merchant_id].append(clean_msg)
        
        # 1. Hostile Check
        if any(w in clean_msg for w in self.hostile_words):
            return "hostile"
            
        # 2. Busy Check
        if any(w in clean_msg for w in self.busy_words):
            return "busy"
            
        # 3. Intent Transition Check
        clean_punct = re.sub(r'[^\w\s]', '', clean_msg)
        if any(w in clean_punct for w in self.intent_words) or clean_msg == "yes":
            return "intent_action"
            
        # 4. Auto-Reply Hell Check
        if merchant_id:
            history = self.merchant_history[merchant_id]
            if len(history) >= 3:
                if history[-1] == history[-2] == history[-3]:
                    return "auto_reply_hell"
                    
        # 5. Regex/heuristic fallback for common auto-replies
        auto_reply_heuristics = {"thank you for contacting", "our team will respond", "out of office", "automated reply"}
        if any(w in clean_msg for w in auto_reply_heuristics):
            return "auto_reply_hell"
            
        return "neutral"

intent_engine = IntentEngine()
