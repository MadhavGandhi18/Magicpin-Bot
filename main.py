import asyncio
import time
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

from config import settings
from models.api_schemas import (
    HealthzResponse, MetadataResponse, ContextRequest, ContextResponse,
    TickRequest, TickResponse, ReplyRequest, ReplyAction
)
from core.state_manager import state_manager
from core.intent_engine import intent_engine
from core.llm_client import llm_client

app = FastAPI(title="Magicpin Vera Bot")
START_TIME = time.time()

@app.get("/v1/healthz", response_model=HealthzResponse)
async def healthz():
    return HealthzResponse(
        status="ok",
        uptime_seconds=int(time.time() - START_TIME),
        contexts_loaded=state_manager.get_context_count()
    )

@app.get("/v1/metadata", response_model=MetadataResponse)
async def metadata():
    return MetadataResponse(
        team_name=settings.team_name,
        team_members=["Candidate"],
        model=settings.model_name,
        approach="Multi-prompt Orchestration with Defensive Intent Middleware",
        contact_email=settings.contact_email,
        version="1.0.0",
        submitted_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    )

@app.post("/v1/context", response_model=ContextResponse)
async def push_context(body: ContextRequest):
    accepted, reason_or_ack, current_version = state_manager.update_context(
        body.scope, body.context_id, body.version, body.payload
    )
    
    if not accepted:
        if current_version is not None:
            return ContextResponse(
                accepted=False,
                reason=reason_or_ack,
                current_version=current_version
            )
        else:
            return ContextResponse(accepted=False, reason=reason_or_ack)
            
    return ContextResponse(
        accepted=True,
        ack_id=reason_or_ack,
        stored_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    )

@app.post("/v1/tick", response_model=TickResponse)
async def handle_tick(body: TickRequest):
    actions = []
    tasks = []
    
    for trg_id in body.available_triggers:
        trigger = state_manager.get_context("trigger", trg_id)
        if not trigger:
            continue
            
        merchant_id = trigger.get('merchant_id')
        if not merchant_id:
            continue
            
        merchant = state_manager.get_context("merchant", merchant_id)
        if not merchant:
            continue
            
        category_slug = merchant.get('category_slug')
        category = state_manager.get_context("category", category_slug)
        if not category:
            continue
            
        customer = None
        customer_id = trigger.get('customer_id')
        if customer_id:
            customer = state_manager.get_context("customer", customer_id)
            
        # Add to async tasks
        tasks.append(llm_client.compose_proactive(trigger, merchant, category, customer))
        
    if not tasks:
        return TickResponse(actions=[])
        
    # Run all generations concurrently, cap at 25s to stay under 30s timeout
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=25.0
        )
        
        for res in results:
            if not isinstance(res, Exception) and res is not None:
                actions.append(res)
    except asyncio.TimeoutError:
        print("Tick timed out!")
        
    return TickResponse(actions=actions)

@app.post("/v1/reply", response_model=ReplyAction)
async def handle_reply(body: ReplyRequest):
    # Update state
    state_manager.append_message(body.conversation_id, body.from_role, body.message)
    
    intent = intent_engine.detect_intent(body.merchant_id, body.conversation_id, body.message)
    if intent == "auto_reply_hell":
        return ReplyAction(action="end", rationale="Detected consecutive auto-replies. Ending conversation to prevent loop.")
    elif intent == "hostile":
        return ReplyAction(action="end", rationale="Merchant response is hostile. Closing conversation gracefully.")
    elif intent == "busy":
        return ReplyAction(action="wait", wait_seconds=10800, rationale="Merchant is busy. Pausing for 3 hours.")
        
    merchant_id = body.merchant_id
    if not merchant_id:
        return ReplyAction(action="end", rationale="Missing merchant_id in reply.")
        
    merchant = state_manager.get_context("merchant", merchant_id)
    category = state_manager.get_context("category", merchant.get("category_slug")) if merchant else None
    trigger = {"kind": "unknown"}
    
    history = state_manager.get_conversation_history(body.conversation_id)
    
    try:
        reply_action = await asyncio.wait_for(
            llm_client.compose_reply(body.conversation_id, history, trigger, merchant, category, intent),
            timeout=25.0
        )
        return reply_action
    except asyncio.TimeoutError:
        return ReplyAction(action="wait", wait_seconds=600, rationale="LLM timeout, waiting 10 minutes before retry.")
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
