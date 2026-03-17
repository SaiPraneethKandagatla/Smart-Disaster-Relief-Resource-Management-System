from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from relief_system import DisasterReliefSystem, safe_load_json, safe_write_json

# MongoDB support (optional)
USE_MONGODB = False
try:
    from db import get_collection, REQUESTS_COLLECTION
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    USE_MONGODB = True
except ImportError:
    pass


RequestStatus = Literal["pending", "approved", "rejected"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data_file_path(filename: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, filename)


REQUESTS_FILE = _data_file_path("requests.json")


def _load_requests() -> List[Dict[str, Any]]:
    """Load requests from MongoDB or JSON."""
    if USE_MONGODB:
        try:
            col = get_collection(REQUESTS_COLLECTION)
            items = list(col.find({}, {"_id": 0}))
            return items if isinstance(items, list) else []
        except (ConnectionFailure, ServerSelectionTimeoutError):
            pass
    # Fallback to JSON
    items = safe_load_json(REQUESTS_FILE, default=[])
    return items if isinstance(items, list) else []


def _save_requests(items: List[Dict[str, Any]]) -> None:
    """Save requests to MongoDB or JSON."""
    if USE_MONGODB:
        try:
            col = get_collection(REQUESTS_COLLECTION)
            col.delete_many({})
            if items:
                col.insert_many(items)
            return
        except (ConnectionFailure, ServerSelectionTimeoutError):
            pass
    # Fallback to JSON
    safe_write_json(REQUESTS_FILE, items)


def list_requests(*, status: Optional[RequestStatus] = None) -> List[Dict[str, Any]]:
    items = _load_requests()

    def ok(item: object) -> bool:
        if not isinstance(item, dict):
            return False
        if status is None:
            return True
        return str(item.get("status")) == status

    result = [r for r in items if ok(r)]
    result.sort(key=lambda r: str(r.get("requested_at") or ""), reverse=True)
    return result


def get_request(request_id: str) -> Optional[Dict[str, Any]]:
    rid = str(request_id)
    for item in list_requests(status=None):
        if str(item.get("id")) == rid:
            return item
    return None


def create_request(*, kind: str, payload: Dict[str, Any], requested_by: str | None = None) -> Dict[str, Any]:
    rid = str(uuid.uuid4())
    req = {
        "id": rid,
        "kind": str(kind),
        "payload": payload or {},
        "status": "pending",
        "requested_by": (str(requested_by).strip() if requested_by else None),
        "requested_at": _now_iso(),
        "decided_at": None,
        "decision_note": None,
        "error": None,
    }

    items = _load_requests()
    items.append(req)
    _save_requests(items)
    return req


def _update_request(request_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    rid = str(request_id)
    items = _load_requests()

    found = None
    for item in items:
        if isinstance(item, dict) and str(item.get("id")) == rid:
            item.update(patch)
            found = item
            break

    if not found:
        raise ValueError("Request not found")

    _save_requests(items)
    return found


def approve_request(*, request_id: str, note: str = "") -> Dict[str, Any]:
    return _update_request(
        request_id,
        {
            "status": "approved",
            "decided_at": _now_iso(),
            "decision_note": str(note).strip() or None,
        },
    )


def reject_request(*, request_id: str, note: str = "") -> Dict[str, Any]:
    return _update_request(
        request_id,
        {
            "status": "rejected",
            "decided_at": _now_iso(),
            "decision_note": str(note).strip() or None,
        },
    )


def mark_request_error(*, request_id: str, error: str) -> Dict[str, Any]:
    return _update_request(
        request_id,
        {
            "error": str(error),
        },
    )


def apply_request(system: DisasterReliefSystem, request_item: Dict[str, Any], selected_responders: List[str] | None = None) -> str:
    """Apply a request to the system.

    Returns a human-friendly summary of what happened.
    selected_responders: Optional list of responder IDs to allocate (for disaster_report).
    """

    if not isinstance(request_item, dict):
        raise ValueError("Invalid request")

    kind = str(request_item.get("kind") or "").strip()
    payload = request_item.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    if kind == "add_camp":
        system.add_camp(
            camp_id=str(payload.get("camp_id", "")).strip(),
            location=str(payload.get("location", "")).strip(),
            max_capacity=int(payload.get("max_capacity", 0)),
            available_food_packets=int(payload.get("available_food_packets", 0)),
            available_medical_kits=int(payload.get("available_medical_kits", 0)),
            volunteers=list(payload.get("volunteers", [])),
        )
        return "Camp added"

    if kind == "register_victim":
        victim = system.register_victim(
            victim_id=str(payload.get("victim_id", "")).strip(),
            name=str(payload.get("name", "")).strip(),
            age=int(payload.get("age", 0)),
            address=str(payload.get("address", "")).strip(),
            health_condition=str(payload.get("health_condition", "normal")).strip().lower(),
            injury=str(payload.get("injury", "")).strip(),
        )
        return f"Victim registered (assigned camp {victim.assigned_camp})"

    if kind == "update_resources":
        system.update_camp_resources(
            camp_id=str(payload.get("camp_id", "")).strip(),
            food_add=int(payload.get("food_add", 0)),
            medical_add=int(payload.get("medical_add", 0)),
        )
        return "Resources updated"

    if kind == "distribute_food":
        count = system.distribute_food()
        return f"Food distributed: {count}"

    if kind == "distribute_medical":
        count = system.distribute_medical()
        return f"Medical kits distributed: {count}"

    if kind == "set_setup":
        dtype = str(payload.get("disaster_type", "")).strip().lower()
        subtype = str(payload.get("disaster_subtype", "")).strip()
        system.set_disaster_type(dtype)
        if subtype:
            system.set_disaster_subtype(subtype)
        return "Setup saved"

    if kind == "update_responder_status":
        system.update_responder_status(
            responder_id=str(payload.get("responder_id", "")).strip(),
            status=str(payload.get("status", "")).strip().lower(),
        )
        return "Responder status updated"

    if kind == "allocate_responder":
        system.allocate_responder(
            responder_id=str(payload.get("responder_id", "")).strip(),
            target_type=str(payload.get("target_type", "")).strip().lower(),
            target_id=str(payload.get("target_id", "")).strip(),
            note=str(payload.get("note", "")).strip(),
            status=str(payload.get("status", "busy")).strip().lower(),
        )
        return "Responder allocated"

    if kind == "unallocate_responder":
        system.unallocate_responder(responder_id=str(payload.get("responder_id", "")).strip())
        return "Responder unallocated"

    if kind == "help_call" or kind == "help_request":
        # Auto-allocate a responder based on the team requested
        team = str(payload.get("team", "")).strip().lower()
        caller = str(payload.get("caller", "")).strip()
        message = str(payload.get("message", "")).strip()
        
        if not team:
            return "Help request acknowledged (no team specified)"
        
        # Find a free responder of the requested team
        free_responders = [r for r in system.responders if r.role == team and r.status == "free"]
        
        if free_responders:
            # Allocate the first free responder
            responder = free_responders[0]
            responder.status = "busy"
            responder.assigned_to_type = "caller"
            responder.assigned_to_id = caller
            responder.assigned_note = f"Help request: {message[:100]}"
            system.save_data()
            return f"Help request approved. {responder.name} ({team}) dispatched to {caller}"
        else:
            return f"Help request acknowledged but no free {team} available. All are busy."

    if kind == "disaster_report":
        dtype = str(payload.get("disaster_type", "")).strip().lower()
        subtype = str(payload.get("disaster_subtype", "")).strip()
        location = str(payload.get("location", "")).strip()
        severity = str(payload.get("severity", "medium")).strip().lower()
        description = str(payload.get("description", "")).strip()
        affected_area = str(payload.get("affected_area", "")).strip()
        estimated_victims = int(payload.get("estimated_victims", 0))
        reported_by = str(payload.get("reported_by", "")).strip()
        proof_image = str(payload.get("proof_image", "")).strip() or None
        request_id = str(request_item.get("id", ""))

        # Set disaster type in system
        system.set_disaster_type(dtype)
        if subtype:
            system.set_disaster_subtype(subtype)

        # Create active disaster for tracking
        disaster = system.create_disaster(
            disaster_type=dtype,
            location=location,
            disaster_subtype=subtype or None,
            severity=severity,
            reported_by=reported_by or None,
            description=description or None,
            affected_area=affected_area or None,
            estimated_victims=estimated_victims,
            request_id=request_id,
            proof_image=proof_image,
        )

        # Allocate admin-selected responders
        allocated = []
        if selected_responders:
            for rid in selected_responders:
                resp = system.responder_by_id(rid)
                if resp and resp.status == "free":
                    system.assign_responder_to_disaster(
                        disaster_id=disaster.disaster_id,
                        responder_id=rid,
                        task_description=f"Disaster response for {subtype or dtype} at {location}",
                    )
                    allocated.append(f"{resp.name} ({resp.role})")

        system.save_data()

        if allocated:
            return f"Disaster {disaster.disaster_id} verified. Teams dispatched to {location}: " + ", ".join(allocated)
        return f"Disaster {disaster.disaster_id} verified at {location}. No responders selected for dispatch."

    raise ValueError(f"Unknown request kind: {kind}")
