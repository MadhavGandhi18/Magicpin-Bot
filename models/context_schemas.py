from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class CategoryVoice(BaseModel):
    tone: str = ""
    vocab_allowed: List[str] = []
    taboos: List[str] = []

class CategoryContext(BaseModel):
    slug: str
    offer_catalog: List[Dict[str, Any]] = []
    voice: CategoryVoice = CategoryVoice()
    peer_stats: Dict[str, Any] = {}
    digest: List[Dict[str, Any]] = []
    seasonal_beats: List[Dict[str, Any]] = []
    trend_signals: List[Dict[str, Any]] = []
    patient_content_library: List[Dict[str, Any]] = []

class MerchantContext(BaseModel):
    merchant_id: str
    category_slug: str = ""
    identity: Dict[str, Any] = {}
    subscription: Dict[str, Any] = {}
    performance: Dict[str, Any] = {}
    offers: List[Dict[str, Any]] = []
    conversation_history: List[Dict[str, Any]] = []
    customer_aggregate: Dict[str, Any] = {}
    signals: List[str] = []

class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    identity: Dict[str, Any] = {}
    relationship: Dict[str, Any] = {}
    state: str = ""
    preferences: Dict[str, Any] = {}
    consent: Dict[str, Any] = {}

class TriggerContext(BaseModel):
    id: str
    scope: str
    kind: str
    source: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    payload: Dict[str, Any] = {}
    urgency: int = 1
    suppression_key: str = ""
    expires_at: str = ""
