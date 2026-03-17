"""Smart Disaster Relief Resource Management System (Core Module)

This module contains the full OOP implementation and JSON persistence.
It is used by both:
- CLI app entrypoints (project.py, project/project.py)
- Web app (web_app.py)

Concepts covered:
- OOP: classes, constructors
- Lists/Dictionaries
- Loops/Conditionals
- File handling (JSON read/write)
- Basic data analysis (report)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

# MongoDB support (optional - falls back to JSON if MongoDB unavailable)
USE_MONGODB = False
try:
    from db import get_collection, CAMPS_COLLECTION, VICTIMS_COLLECTION, SETTINGS_COLLECTION, RESPONDERS_COLLECTION
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    USE_MONGODB = True
except ImportError:
    pass


DISASTER_TYPES = {"natural", "man_made"}
RESPONDER_STATUSES = {"free", "busy", "in_operation"}


MAN_MADE_DISASTERS: List[Dict[str, str]] = [
    {"code": "building_fire", "label": "Building / Urban Fire"},
    {"code": "road_accident", "label": "Road Traffic Accident"},
    {"code": "train_derailment", "label": "Train Derailment"},
    {"code": "industrial_accident", "label": "Industrial Accident"},
    {"code": "chemical_spill", "label": "Industrial Chemical Spill"},
    {"code": "gas_leak", "label": "Gas Leak"},
    {"code": "oil_spill", "label": "Oil Spill"},
    {"code": "explosion", "label": "Explosion"},
    {"code": "nuclear_radiological", "label": "Nuclear / Radiological Incident"},
    {"code": "stampede", "label": "Crowd Stampede"},
]


NATURAL_DISASTERS: List[Dict[str, str]] = [
    {"code": "earthquake", "label": "Earthquake"},
    {"code": "flood", "label": "Flood"},
    {"code": "cyclone", "label": "Cyclone / Hurricane"},
    {"code": "tsunami", "label": "Tsunami"},
    {"code": "landslide", "label": "Landslide"},
    {"code": "wildfire", "label": "Wildfire"},
    {"code": "drought", "label": "Drought / Heatwave"},
]


DEFAULT_ROLE_PERMISSIONS: Dict[str, bool] = {
    "doctor": True,
    "fire_force": True,
    "police": True,
    "diver": True,
    "ambulance": True,
}


DEFAULT_EMERGENCY_CONTACTS: Dict[str, str] = {
    # Leave values empty by default; admin can configure per region.
    "toll_free": "",
    "ambulance": "",
    "police": "",
    "fire_force": "",
    "doctor": "",
    "diver": "",
}


def _data_file_path(filename: str) -> str:
    """Return an absolute path for a persistent data file stored at workspace root."""

    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, filename)


def safe_load_json(path: str, default):
    """Load JSON from path, returning default if file doesn't exist or is invalid."""

    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return default


def safe_write_json(path: str, data) -> None:
    """Write JSON to disk."""

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


@dataclass
class ReliefCamp:
    """Represents a relief camp and its resources."""

    camp_id: str
    location: str
    max_capacity: int
    current_occupancy: int
    available_food_packets: int
    available_medical_kits: int
    volunteers: List[str]
    deadline: Optional[str] = None  # ISO format date string (e.g., "2026-03-15")
    status: str = "active"  # active | expired | closed

    def check_capacity(self) -> bool:
        """Return True if camp can accept more victims."""

        return self.current_occupancy < self.max_capacity

    def is_expired(self) -> bool:
        """Check if camp has passed its deadline."""
        if not self.deadline:
            return False
        try:
            from datetime import datetime
            deadline_date = datetime.fromisoformat(self.deadline.replace('Z', '+00:00'))
            return datetime.now(deadline_date.tzinfo or None) > deadline_date
        except (ValueError, TypeError):
            return False

    def update_resources(self, *, food_delta: int = 0, medical_delta: int = 0) -> None:
        """Update resource quantities (positive adds, negative subtracts)."""

        self.available_food_packets = max(0, self.available_food_packets + food_delta)
        self.available_medical_kits = max(0, self.available_medical_kits + medical_delta)

    def to_dict(self) -> Dict:
        return {
            "camp_id": self.camp_id,
            "location": self.location,
            "max_capacity": self.max_capacity,
            "current_occupancy": self.current_occupancy,
            "available_food_packets": self.available_food_packets,
            "available_medical_kits": self.available_medical_kits,
            "volunteers": self.volunteers,
            "deadline": self.deadline,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ReliefCamp":
        return cls(
            camp_id=str(data.get("camp_id", "")),
            location=str(data.get("location", "")),
            max_capacity=int(data.get("max_capacity", 0)),
            current_occupancy=int(data.get("current_occupancy", 0)),
            available_food_packets=int(data.get("available_food_packets", 0)),
            available_medical_kits=int(data.get("available_medical_kits", 0)),
            volunteers=list(data.get("volunteers", [])),
            deadline=data.get("deadline"),
            status=str(data.get("status", "active")),
        )


@dataclass
class Victim:
    """Represents a disaster victim."""

    victim_id: str
    name: str
    age: int
    address: str
    health_condition: str  # "normal" or "critical"
    injury: str
    assigned_camp: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_specialty: Optional[str] = None
    food_received: bool = False
    medical_received: bool = False

    def to_dict(self) -> Dict:
        return {
            "victim_id": self.victim_id,
            "name": self.name,
            "age": self.age,
            "address": self.address,
            "health_condition": self.health_condition,
            "injury": self.injury,
            "doctor_name": self.doctor_name,
            "doctor_specialty": self.doctor_specialty,
            "assigned_camp": self.assigned_camp,
            "food_received": self.food_received,
            "medical_received": self.medical_received,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Victim":
        return cls(
            victim_id=str(data.get("victim_id", "")),
            name=str(data.get("name", "")),
            age=int(data.get("age", 0)),
            address=str(data.get("address", "")),
            health_condition=str(data.get("health_condition", "normal")).lower(),
            injury=str(data.get("injury", "")),
            doctor_name=data.get("doctor_name"),
            doctor_specialty=data.get("doctor_specialty"),
            assigned_camp=data.get("assigned_camp"),
            food_received=bool(data.get("food_received", False)),
            medical_received=bool(data.get("medical_received", False)),
        )


@dataclass
class Responder:
    """Represents an emergency responder (doctor/fire/police/diver)."""

    responder_id: str
    name: str
    role: str  # doctor | fire_force | police | diver | ambulance
    specialty: Optional[str] = None
    status: str = "free"  # free | busy | in_operation
    capabilities: List[str] = None
    assigned_to_type: Optional[str] = None  # victim | camp | disaster
    assigned_to_id: Optional[str] = None
    assigned_note: Optional[str] = None
    assigned_at: Optional[str] = None  # ISO timestamp when assigned
    estimated_duration_minutes: Optional[int] = None  # Estimated task duration
    task_description: Optional[str] = None  # Description of current task

    def __post_init__(self) -> None:
        if self.capabilities is None:
            self.capabilities = []
        self.status = str(self.status or "free").lower()
        if self.status not in RESPONDER_STATUSES:
            self.status = "free"

    def to_dict(self) -> Dict:
        return {
            "responder_id": self.responder_id,
            "name": self.name,
            "role": self.role,
            "specialty": self.specialty,
            "status": self.status,
            "capabilities": list(self.capabilities or []),
            "assigned_to_type": self.assigned_to_type,
            "assigned_to_id": self.assigned_to_id,
            "assigned_note": self.assigned_note,
            "assigned_at": self.assigned_at,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "task_description": self.task_description,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Responder":
        return cls(
            responder_id=str(data.get("responder_id", "")),
            name=str(data.get("name", "")),
            role=str(data.get("role", "")),
            specialty=data.get("specialty"),
            status=str(data.get("status", "free")),
            capabilities=list(data.get("capabilities", []) or []),
            assigned_to_type=data.get("assigned_to_type"),
            assigned_to_id=data.get("assigned_to_id"),
            assigned_note=data.get("assigned_note"),
            assigned_at=data.get("assigned_at"),
            estimated_duration_minutes=data.get("estimated_duration_minutes"),
            task_description=data.get("task_description"),
        )


@dataclass
class Volunteer:
    """Represents a volunteer worker assigned to relief camps."""

    volunteer_id: str
    name: str
    assigned_camp: Optional[str] = None
    task: Optional[str] = None  # e.g., "Food Distribution", "Medical Support", "Registration"

    def to_dict(self) -> Dict:
        return {
            "volunteer_id": self.volunteer_id,
            "name": self.name,
            "assigned_camp": self.assigned_camp,
            "task": self.task,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Volunteer":
        return cls(
            volunteer_id=str(data.get("volunteer_id", "")),
            name=str(data.get("name", "")),
            assigned_camp=data.get("assigned_camp"),
            task=data.get("task"),
        )


# Disaster status constants
DISASTER_STATUSES = {"reported", "ongoing", "contained", "resolved", "closed"}


@dataclass
class ActiveDisaster:
    """Represents an active/tracked disaster incident."""

    disaster_id: str
    disaster_type: str  # flood | earthquake | fire | cyclone
    disaster_subtype: Optional[str] = None
    location: str = ""
    severity: str = "medium"  # low | medium | high | critical
    status: str = "ongoing"  # reported | ongoing | contained | resolved | closed
    reported_at: Optional[str] = None
    approved_at: Optional[str] = None
    resolved_at: Optional[str] = None
    reported_by: Optional[str] = None
    description: Optional[str] = None
    affected_area: Optional[str] = None
    estimated_victims: int = 0
    assigned_responders: List[str] = None  # List of responder IDs
    assigned_camps: List[str] = None  # List of camp IDs
    updates: List[Dict[str, str]] = None  # List of status updates with timestamps
    request_id: Optional[str] = None  # Link to original request
    proof_image: Optional[str] = None  # Static path for uploaded proof image
    resource_needs: List[Dict] = None  # Resource needs tracker

    def __post_init__(self) -> None:
        if self.assigned_responders is None:
            self.assigned_responders = []
        if self.assigned_camps is None:
            self.assigned_camps = []
        if self.updates is None:
            self.updates = []
        if self.resource_needs is None:
            self.resource_needs = []
        self.status = str(self.status or "ongoing").lower()
        if self.status not in DISASTER_STATUSES:
            self.status = "ongoing"

    def add_update(self, message: str, updated_by: str = "System") -> None:
        """Add a status update to the disaster."""
        from datetime import datetime
        self.updates.append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "updated_by": updated_by,
        })

    def to_dict(self) -> Dict:
        return {
            "disaster_id": self.disaster_id,
            "disaster_type": self.disaster_type,
            "disaster_subtype": self.disaster_subtype,
            "location": self.location,
            "severity": self.severity,
            "status": self.status,
            "reported_at": self.reported_at,
            "approved_at": self.approved_at,
            "resolved_at": self.resolved_at,
            "reported_by": self.reported_by,
            "description": self.description,
            "affected_area": self.affected_area,
            "estimated_victims": self.estimated_victims,
            "assigned_responders": list(self.assigned_responders or []),
            "assigned_camps": list(self.assigned_camps or []),
            "updates": list(self.updates or []),
            "request_id": self.request_id,
            "proof_image": self.proof_image,
            "resource_needs": list(self.resource_needs or []),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ActiveDisaster":
        return cls(
            disaster_id=str(data.get("disaster_id", "")),
            disaster_type=str(data.get("disaster_type", "")),
            disaster_subtype=data.get("disaster_subtype"),
            location=str(data.get("location", "")),
            severity=str(data.get("severity", "medium")),
            status=str(data.get("status", "ongoing")),
            reported_at=data.get("reported_at"),
            approved_at=data.get("approved_at"),
            resolved_at=data.get("resolved_at"),
            reported_by=data.get("reported_by"),
            description=data.get("description"),
            affected_area=data.get("affected_area"),
            estimated_victims=int(data.get("estimated_victims", 0)),
            assigned_responders=list(data.get("assigned_responders", []) or []),
            assigned_camps=list(data.get("assigned_camps", []) or []),
            updates=list(data.get("updates", []) or []),
            request_id=data.get("request_id"),
            proof_image=data.get("proof_image"),
            resource_needs=list(data.get("resource_needs", []) or []),
        )


class DisasterReliefSystem:
    """Main controller: stores data, performs operations, generates report."""

    # Very small built-in doctor pool for demo/college project.
    # A real system would store doctors in a database.
    DOCTORS: List[Dict[str, str]] = [
        {"name": "Dr. Asha", "specialty": "Emergency"},
        {"name": "Dr. Ravi", "specialty": "Orthopedic"},
        {"name": "Dr. Meera", "specialty": "Burn Care"},
        {"name": "Dr. John", "specialty": "Cardiology"},
        {"name": "Dr. Fatima", "specialty": "Neurology"},
        {"name": "Dr. Chen", "specialty": "Respiratory"},
    ]

    CAMPS_FILE = _data_file_path("camps.json")
    VICTIMS_FILE = _data_file_path("victims.json")
    SETTINGS_FILE = _data_file_path("settings.json")
    RESPONDERS_FILE = _data_file_path("responders.json")
    VOLUNTEERS_FILE = _data_file_path("volunteers.json")
    VOLUNTEERS_TXT_FILE = _data_file_path("volunteers.txt")
    DISTRIBUTION_LOG_FILE = _data_file_path("distribution_log.txt")
    DISASTERS_FILE = _data_file_path("disasters.json")

    def __init__(self) -> None:
        self.camps: List[ReliefCamp] = []
        self.victims: List[Victim] = []
        self.settings: Dict[str, object] = {}
        self.responders: List[Responder] = []
        self.volunteers: List[Volunteer] = []
        self.active_disasters: List[ActiveDisaster] = []
        self.load_data()

    # ----------------------------- Persistence -----------------------------
    def load_data(self) -> None:
        """Load data from MongoDB (if available) or JSON files."""

        if USE_MONGODB:
            try:
                camps_col = get_collection(CAMPS_COLLECTION)
                victims_col = get_collection(VICTIMS_COLLECTION)
                settings_col = get_collection(SETTINGS_COLLECTION)
                responders_col = get_collection(RESPONDERS_COLLECTION)

                camps_data = list(camps_col.find({}, {"_id": 0}))
                victims_data = list(victims_col.find({}, {"_id": 0}))
                settings_doc = settings_col.find_one({"_id": "config"}) or {}
                settings_doc.pop("_id", None)
                responders_data = list(responders_col.find({}, {"_id": 0}))

                # Load volunteers from MongoDB if collection exists
                try:
                    volunteers_col = get_collection("volunteers")
                    volunteers_data = list(volunteers_col.find({}, {"_id": 0}))
                except Exception:
                    volunteers_data = []

                # Load active disasters from MongoDB if collection exists
                try:
                    disasters_col = get_collection("disasters")
                    disasters_data = list(disasters_col.find({}, {"_id": 0}))
                except Exception:
                    disasters_data = []

                self.camps = [ReliefCamp.from_dict(item) for item in camps_data if isinstance(item, dict)]
                self.victims = [Victim.from_dict(item) for item in victims_data if isinstance(item, dict)]
                self.settings = settings_doc if isinstance(settings_doc, dict) else {}
                self.responders = [Responder.from_dict(item) for item in responders_data if isinstance(item, dict)]
                self.volunteers = [Volunteer.from_dict(item) for item in volunteers_data if isinstance(item, dict)]
                self.active_disasters = [ActiveDisaster.from_dict(item) for item in disasters_data if isinstance(item, dict)]
                self._ensure_default_responders()
                self._recompute_occupancies()
                return
            except (ConnectionFailure, ServerSelectionTimeoutError):
                print("MongoDB unavailable, falling back to JSON files")

        # Fallback to JSON
        camps_data = safe_load_json(self.CAMPS_FILE, default=[])
        victims_data = safe_load_json(self.VICTIMS_FILE, default=[])
        settings_data = safe_load_json(self.SETTINGS_FILE, default={})
        responders_data = safe_load_json(self.RESPONDERS_FILE, default=[])
        volunteers_data = safe_load_json(self.VOLUNTEERS_FILE, default=[])
        disasters_data = safe_load_json(self.DISASTERS_FILE, default=[])

        self.camps = [ReliefCamp.from_dict(item) for item in camps_data if isinstance(item, dict)]
        self.victims = [Victim.from_dict(item) for item in victims_data if isinstance(item, dict)]
        self.settings = settings_data if isinstance(settings_data, dict) else {}
        self.responders = [Responder.from_dict(item) for item in responders_data if isinstance(item, dict)]
        self.volunteers = [Volunteer.from_dict(item) for item in volunteers_data if isinstance(item, dict)]
        self.active_disasters = [ActiveDisaster.from_dict(item) for item in disasters_data if isinstance(item, dict)]
        self._ensure_default_responders()
        self._recompute_occupancies()

    def save_data(self) -> None:
        """Save data to MongoDB (if available) or JSON files."""

        if USE_MONGODB:
            try:
                camps_col = get_collection(CAMPS_COLLECTION)
                victims_col = get_collection(VICTIMS_COLLECTION)
                settings_col = get_collection(SETTINGS_COLLECTION)
                responders_col = get_collection(RESPONDERS_COLLECTION)

                # Clear and re-insert camps
                camps_col.delete_many({})
                if self.camps:
                    camps_col.insert_many([c.to_dict() for c in self.camps])

                # Clear and re-insert victims
                victims_col.delete_many({})
                if self.victims:
                    victims_col.insert_many([v.to_dict() for v in self.victims])

                # Upsert settings as single document
                settings_col.replace_one(
                    {"_id": "config"},
                    {**self.settings, "_id": "config"},
                    upsert=True
                )

                # Clear and re-insert responders
                responders_col.delete_many({})
                if self.responders:
                    responders_col.insert_many([r.to_dict() for r in self.responders])

                # Clear and re-insert volunteers
                try:
                    volunteers_col = get_collection("volunteers")
                    volunteers_col.delete_many({})
                    if self.volunteers:
                        volunteers_col.insert_many([v.to_dict() for v in self.volunteers])
                except Exception as e:
                    print(f"Error saving volunteers to MongoDB: {e}")

                # Clear and re-insert active disasters
                try:
                    disasters_col = get_collection("disasters")
                    disasters_col.delete_many({})
                    if self.active_disasters:
                        disasters_col.insert_many([d.to_dict() for d in self.active_disasters])
                except Exception as e:
                    print(f"Error saving disasters to MongoDB: {e}")

                # Also save volunteers to text file for file handling requirement
                self._save_volunteers_to_txt()

                return
            except (ConnectionFailure, ServerSelectionTimeoutError):
                print("MongoDB unavailable, falling back to JSON files")

        # Fallback to JSON
        safe_write_json(self.CAMPS_FILE, [c.to_dict() for c in self.camps])
        safe_write_json(self.VICTIMS_FILE, [v.to_dict() for v in self.victims])
        safe_write_json(self.SETTINGS_FILE, self.settings)
        safe_write_json(self.RESPONDERS_FILE, [r.to_dict() for r in self.responders])
        safe_write_json(self.VOLUNTEERS_FILE, [v.to_dict() for v in self.volunteers])
        safe_write_json(self.DISASTERS_FILE, [d.to_dict() for d in self.active_disasters])
        
        # Also save volunteers to text file for file handling requirement
        self._save_volunteers_to_txt()

    # ----------------------------- Admin Permissions -----------------------------
    def get_role_permissions(self) -> Dict[str, bool]:
        """Return role permissions (admin-controlled), with defaults applied."""

        raw = self.settings.get("role_permissions")
        if not isinstance(raw, dict):
            raw = {}
        merged = dict(DEFAULT_ROLE_PERMISSIONS)
        for key, value in raw.items():
            merged[str(key).lower()] = bool(value)
        return merged

    def set_role_permissions(self, permissions: Dict[str, object]) -> None:
        merged = dict(DEFAULT_ROLE_PERMISSIONS)
        for key, value in (permissions or {}).items():
            merged[str(key).lower()] = bool(value)
        self.settings["role_permissions"] = merged
        self.save_data()

    # ----------------------------- Emergency Contacts -----------------------------
    def get_emergency_contacts(self) -> Dict[str, str]:
        raw = self.settings.get("emergency_contacts")
        if not isinstance(raw, dict):
            raw = {}

        merged = dict(DEFAULT_EMERGENCY_CONTACTS)
        for key, value in raw.items():
            merged[str(key)] = str(value) if value is not None else ""
        return merged

    def set_emergency_contacts(self, contacts: Dict[str, object]) -> None:
        merged = dict(DEFAULT_EMERGENCY_CONTACTS)
        for key, value in (contacts or {}).items():
            k = str(key)
            if k in merged:
                merged[k] = str(value).strip()
        self.settings["emergency_contacts"] = merged
        self.save_data()

    def can_manage_role(self, role: str) -> bool:
        role_key = str(role).strip().lower()
        return bool(self.get_role_permissions().get(role_key, False))

    # ----------------------------- Settings (Disaster Type) -----------------------------
    def get_disaster_type(self) -> Optional[str]:
        value = self.settings.get("disaster_type")
        if isinstance(value, str) and value in DISASTER_TYPES:
            return value
        return None

    def set_disaster_type(self, disaster_type: str) -> None:
        value = str(disaster_type).strip().lower()
        if value not in DISASTER_TYPES:
            raise ValueError("Disaster type must be 'natural' or 'man_made'")
        self.settings["disaster_type"] = value
        # If type changed, clear subtype if it doesn't match.
        subtype = self.get_disaster_subtype()
        if subtype and subtype not in {d["code"] for d in self.list_disaster_subtypes(value)}:
            self.settings.pop("disaster_subtype", None)
        self.save_data()

    def list_disaster_subtypes(self, disaster_type: str) -> List[Dict[str, str]]:
        dtype = str(disaster_type).strip().lower()
        if dtype == "man_made":
            return list(MAN_MADE_DISASTERS)
        if dtype == "natural":
            return list(NATURAL_DISASTERS)
        return []

    def get_disaster_subtype(self) -> Optional[str]:
        value = self.settings.get("disaster_subtype")
        return str(value) if isinstance(value, str) and value.strip() else None

    def set_disaster_subtype(self, disaster_subtype: str) -> None:
        dtype = self.get_disaster_type()
        if not dtype:
            raise ValueError("Set disaster type first")

        code = str(disaster_subtype).strip()
        valid_codes = {d["code"] for d in self.list_disaster_subtypes(dtype)}
        if code not in valid_codes:
            raise ValueError("Invalid disaster type selection")

        self.settings["disaster_subtype"] = code
        self.save_data()

    def disaster_subtype_label(self) -> Optional[str]:
        dtype = self.get_disaster_type()
        sub = self.get_disaster_subtype()
        if not dtype or not sub:
            return None
        for item in self.list_disaster_subtypes(dtype):
            if item.get("code") == sub:
                return str(item.get("label") or sub)
        return sub

    def activated_roles_for_disaster(self) -> List[str]:
        """Return which teams should be dispatched based on disaster type."""

        dtype = self.get_disaster_type()
        subtype = self.get_disaster_subtype() or ""

        if not dtype:
            return []

        # Ambulance is always dispatched once setup is chosen.
        roles: List[str] = ["ambulance"]

        if dtype == "man_made":
            roles.extend(["police", "doctor", "fire_force"])
            if subtype in {"chemical_spill", "gas_leak", "oil_spill", "nuclear_radiological"}:
                roles.append("fire_force")
            return sorted(set(roles), key=roles.index)

        # natural
        roles.extend(["doctor", "police", "fire_force"])
        if subtype in {"flood", "tsunami"}:
            roles.append("diver")
        return sorted(set(roles), key=roles.index)

    # ----------------------------- Responders -----------------------------
    def _ensure_default_responders(self) -> None:
        """Create a default roster if responders.json is missing/empty."""

        responders: List[Responder] = []

        if not self.responders:
            for idx, doctor in enumerate(self.DOCTORS, start=1):
                responders.append(
                    Responder(
                        responder_id=f"doctor-{idx}",
                        name=doctor["name"],
                        role="doctor",
                        specialty=doctor["specialty"],
                        status="free",
                        capabilities=["triage", "emergency_care"],
                    )
                )

            for idx in range(1, 5):
                responders.append(
                    Responder(
                        responder_id=f"fire-{idx}",
                        name=f"Fire Team {idx}",
                        role="fire_force",
                        specialty="Rescue",
                        status="free",
                        capabilities=["fire_suppression", "rescue", "first_aid"],
                    )
                )

            for idx in range(1, 5):
                responders.append(
                    Responder(
                        responder_id=f"police-{idx}",
                        name=f"Police Unit {idx}",
                        role="police",
                        specialty="Security",
                        status="free",
                        capabilities=["crowd_control", "traffic_control", "security"],
                    )
                )

            for idx in range(1, 4):
                responders.append(
                    Responder(
                        responder_id=f"diver-{idx}",
                        name=f"Diver Rescue {idx}",
                        role="diver",
                        specialty="Water Rescue",
                        status="free",
                        capabilities=[
                            "strong_swimmer",
                            "underwater_rescue",
                            "long_duration_in_water",
                        ],
                    )
                )

            for idx in range(1, 5):
                responders.append(
                    Responder(
                        responder_id=f"ambulance-{idx}",
                        name=f"Ambulance Unit {idx}",
                        role="ambulance",
                        specialty="EMS",
                        status="free",
                        capabilities=["patient_transport", "basic_life_support", "triage"],
                    )
                )

            self.responders = responders
            self.save_data()
            return

        # Backfill new responder teams into existing rosters.
        existing_roles = {r.role for r in self.responders}
        existing_ids = {r.responder_id for r in self.responders}

        if "ambulance" not in existing_roles:
            for idx in range(1, 5):
                rid = f"ambulance-{idx}"
                if rid in existing_ids:
                    continue
                responders.append(
                    Responder(
                        responder_id=rid,
                        name=f"Ambulance Unit {idx}",
                        role="ambulance",
                        specialty="EMS",
                        status="free",
                        capabilities=["patient_transport", "basic_life_support", "triage"],
                    )
                )

        if responders:
            self.responders.extend(responders)
            self.save_data()

    def responders_by_role(self, role: Optional[str] = None) -> List[Responder]:
        if not role:
            return list(self.responders)
        wanted = str(role).strip().lower()
        return [r for r in self.responders if r.role.lower() == wanted]

    def responder_by_id(self, responder_id: str) -> Optional[Responder]:
        rid = str(responder_id)
        for responder in self.responders:
            if responder.responder_id == rid:
                return responder
        return None

    def _doctor_responder_by_name(self, doctor_name: str) -> Optional[Responder]:
        name = str(doctor_name).strip()
        for responder in self.responders:
            if responder.role == "doctor" and responder.name == name:
                return responder
        return None

    def update_responder_status(self, *, responder_id: str, status: str) -> None:
        responder = self.responder_by_id(responder_id)
        if not responder:
            raise ValueError("Responder not found")

        if not self.can_manage_role(responder.role):
            raise PermissionError(f"Admin permission denied for role: {responder.role}")

        value = str(status).strip().lower()
        if value not in RESPONDER_STATUSES:
            raise ValueError("Status must be free, busy, or in_operation")

        # If doctor was treating a victim and now becoming free, mark victim as recovered
        if responder.role == "doctor" and responder.status in {"busy", "in_operation"} and value == "free":
            if responder.assigned_to_type == "victim" and responder.assigned_to_id:
                victim = self.victim_by_id(responder.assigned_to_id)
                if victim and victim.health_condition == "critical":
                    victim.health_condition = "normal"

        responder.status = value
        if responder.status == "free":
            responder.assigned_to_type = None
            responder.assigned_to_id = None
            responder.assigned_note = None
        self.save_data()

    def allocate_responder(
        self,
        *,
        responder_id: str,
        target_type: str,
        target_id: str,
        note: str = "",
        status: str = "busy",
        estimated_duration_minutes: Optional[int] = None,
        task_description: Optional[str] = None,
    ) -> None:
        """Assign a responder to a target (victim/camp) and persist in responders.json."""
        from datetime import datetime

        responder = self.responder_by_id(responder_id)
        if not responder:
            raise ValueError("Responder not found")

        if not self.can_manage_role(responder.role):
            raise PermissionError(f"Admin permission denied for role: {responder.role}")

        ttype = str(target_type).strip().lower()
        tid = str(target_id).strip()
        if ttype not in {"victim", "camp", "disaster"}:
            raise ValueError("Target type must be victim, camp, or disaster")
        if not tid:
            raise ValueError("Target ID is required")

        if ttype == "victim" and not self.victim_by_id(tid):
            raise ValueError("Victim not found")
        if ttype == "camp" and not self.camp_by_id(tid):
            raise ValueError("Camp not found")

        svalue = str(status).strip().lower()
        if svalue not in RESPONDER_STATUSES:
            raise ValueError("Status must be free, busy, or in_operation")
        if svalue == "free":
            svalue = "busy"

        responder.assigned_to_type = ttype
        responder.assigned_to_id = tid
        responder.assigned_note = str(note).strip() or None
        responder.status = svalue
        responder.assigned_at = datetime.now().isoformat()
        responder.estimated_duration_minutes = estimated_duration_minutes
        responder.task_description = task_description or note or None
        self.save_data()

    def unallocate_responder(self, *, responder_id: str) -> None:
        responder = self.responder_by_id(responder_id)
        if not responder:
            raise ValueError("Responder not found")
        if not self.can_manage_role(responder.role):
            raise PermissionError(f"Admin permission denied for role: {responder.role}")

        # If doctor was treating a victim, mark victim as recovered
        if responder.role == "doctor" and responder.status in {"busy", "in_operation"}:
            if responder.assigned_to_type == "victim" and responder.assigned_to_id:
                victim = self.victim_by_id(responder.assigned_to_id)
                if victim and victim.health_condition == "critical":
                    victim.health_condition = "normal"
                    victim.doctor_name = None
                    victim.doctor_specialty = None

        responder.assigned_to_type = None
        responder.assigned_to_id = None
        responder.assigned_note = None
        responder.status = "free"
        responder.assigned_at = None
        responder.estimated_duration_minutes = None
        responder.task_description = None
        self.save_data()

    def complete_responder_task(self, *, responder_id: str) -> Dict[str, object]:
        """Mark a responder's task as complete and set status to free.
        
        Returns details about the completed task.
        """
        responder = self.responder_by_id(responder_id)
        if not responder:
            raise ValueError("Responder not found")
        
        if responder.status == "free":
            raise ValueError("Responder is already free")

        # Store task details for return
        task_details = {
            "responder_id": responder.responder_id,
            "responder_name": responder.name,
            "role": responder.role,
            "previous_status": responder.status,
            "task_type": responder.assigned_to_type,
            "task_target": responder.assigned_to_id,
            "task_description": responder.task_description,
            "assigned_at": responder.assigned_at,
        }

        # If doctor was treating a victim, update victim record
        if responder.role == "doctor" and responder.assigned_to_type == "victim":
            victim = self.victim_by_id(responder.assigned_to_id) if responder.assigned_to_id else None
            if victim:
                # Mark victim as recovered if critical
                if victim.health_condition == "critical":
                    victim.health_condition = "normal"
                victim.doctor_name = None
                victim.doctor_specialty = None

        # Clear assignment and set to free
        responder.assigned_to_type = None
        responder.assigned_to_id = None
        responder.assigned_note = None
        responder.status = "free"
        responder.assigned_at = None
        responder.estimated_duration_minutes = None
        responder.task_description = None
        
        self.save_data()
        return task_details

    def get_busy_responders(self) -> List[Dict[str, object]]:
        """Get all responders who are currently busy or in operation with task details."""
        from datetime import datetime
        
        busy_list = []
        for r in self.responders:
            if r.status in {"busy", "in_operation"}:
                # Calculate elapsed time
                elapsed_minutes = None
                time_remaining = None
                is_overdue = False
                
                if r.assigned_at:
                    try:
                        start_time = datetime.fromisoformat(r.assigned_at)
                        elapsed = datetime.now() - start_time
                        elapsed_minutes = int(elapsed.total_seconds() / 60)
                        
                        if r.estimated_duration_minutes:
                            time_remaining = r.estimated_duration_minutes - elapsed_minutes
                            is_overdue = time_remaining < 0
                    except (ValueError, TypeError):
                        pass
                
                busy_list.append({
                    "responder_id": r.responder_id,
                    "name": r.name,
                    "role": r.role,
                    "specialty": r.specialty,
                    "status": r.status,
                    "assigned_to_type": r.assigned_to_type,
                    "assigned_to_id": r.assigned_to_id,
                    "task_description": r.task_description or r.assigned_note,
                    "assigned_at": r.assigned_at,
                    "estimated_duration_minutes": r.estimated_duration_minutes,
                    "elapsed_minutes": elapsed_minutes,
                    "time_remaining": time_remaining,
                    "is_overdue": is_overdue,
                })
        
        return busy_list

    def auto_complete_overdue_tasks(self) -> List[Dict[str, object]]:
        """Automatically complete tasks for responders whose estimated duration has passed.
        
        Returns list of auto-completed tasks.
        """
        from datetime import datetime
        
        completed = []
        for r in self.responders:
            if r.status not in {"busy", "in_operation"}:
                continue
            if not r.assigned_at or not r.estimated_duration_minutes:
                continue
            
            try:
                start_time = datetime.fromisoformat(r.assigned_at)
                elapsed = datetime.now() - start_time
                elapsed_minutes = elapsed.total_seconds() / 60
                
                if elapsed_minutes >= r.estimated_duration_minutes:
                    task_details = self.complete_responder_task(responder_id=r.responder_id)
                    task_details["auto_completed"] = True
                    completed.append(task_details)
            except (ValueError, TypeError):
                continue
        
        return completed

    def status_counts(self, *, role: Optional[str] = None) -> Dict[str, int]:
        responders = self.responders_by_role(role)
        counts = {"free": 0, "busy": 0, "in_operation": 0}
        for responder in responders:
            if responder.status in counts:
                counts[responder.status] += 1
        return counts

    def _recompute_occupancies(self) -> None:
        counts: Dict[str, int] = {}
        for victim in self.victims:
            if victim.assigned_camp:
                counts[victim.assigned_camp] = counts.get(victim.assigned_camp, 0) + 1

        for camp in self.camps:
            camp.current_occupancy = counts.get(camp.camp_id, 0)

    # ----------------------------- Lookups -----------------------------
    def camp_by_id(self, camp_id: str) -> Optional[ReliefCamp]:
        for camp in self.camps:
            if camp.camp_id == camp_id:
                return camp
        return None

    def victim_by_id(self, victim_id: str) -> Optional[Victim]:
        for victim in self.victims:
            if victim.victim_id == victim_id:
                return victim
        return None

    def search_victims(self, query: str) -> List[Victim]:
        """Search victims by name or ID (case-insensitive partial match)."""
        if not query:
            return []
        q = query.lower().strip()
        results = []
        for v in self.victims:
            if q in v.victim_id.lower() or q in v.name.lower():
                results.append(v)
        return results

    def get_low_resource_alerts(self, food_threshold: int = 10, medical_threshold: int = 5) -> List[Dict[str, Any]]:
        """Return list of camps with low resources."""
        alerts = []
        for camp in self.camps:
            if camp.status == "closed" or camp.is_expired():
                continue
            if camp.available_food_packets < food_threshold:
                alerts.append({
                    "camp_id": camp.camp_id,
                    "location": camp.location,
                    "type": "food",
                    "current": camp.available_food_packets,
                    "threshold": food_threshold,
                })
            if camp.available_medical_kits < medical_threshold:
                alerts.append({
                    "camp_id": camp.camp_id,
                    "location": camp.location,
                    "type": "medical",
                    "current": camp.available_medical_kits,
                    "threshold": medical_threshold,
                })
        return alerts

    # ----------------------------- Core Operations -----------------------------
    def add_camp(
        self,
        *,
        camp_id: str,
        location: str,
        max_capacity: int,
        available_food_packets: int,
        available_medical_kits: int,
        volunteers: List[str],
        deadline: Optional[str] = None,
    ) -> None:
        if any(c.camp_id == camp_id for c in self.camps):
            raise ValueError("Camp ID already exists")

        camp = ReliefCamp(
            camp_id=camp_id,
            location=location,
            max_capacity=max_capacity,
            current_occupancy=0,
            available_food_packets=available_food_packets,
            available_medical_kits=available_medical_kits,
            volunteers=volunteers,
            deadline=deadline,
            status="active",
        )
        self.camps.append(camp)
        self.save_data()

    def delete_camp(self, *, camp_id: str, force: bool = False) -> None:
        """Delete a camp. If force=False, only allows deletion if camp is empty or closed/expired."""
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")

        if not force:
            if camp.current_occupancy > 0:
                raise ValueError(f"Camp has {camp.current_occupancy} victims. Relocate them first or use force delete.")
            if camp.status == "active" and not camp.is_expired():
                raise ValueError("Camp is still active. Close it first or wait for deadline.")

        # Remove victims assigned to this camp
        self.victims = [v for v in self.victims if v.assigned_camp != camp_id]

        # Remove the camp
        self.camps = [c for c in self.camps if c.camp_id != camp_id]
        self.save_data()

    def close_camp(self, *, camp_id: str) -> None:
        """Mark a camp as closed (disaster over or no longer needed)."""
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")
        camp.status = "closed"
        self.save_data()

    def reopen_camp(self, *, camp_id: str) -> None:
        """Reopen a closed or expired camp."""
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")
        camp.status = "active"
        self.save_data()

    def update_camp_deadline(self, *, camp_id: str, deadline: Optional[str]) -> None:
        """Update or remove the deadline for a camp."""
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")
        camp.deadline = deadline
        self.save_data()

    def get_expired_camps(self) -> List[ReliefCamp]:
        """Get all camps that have passed their deadline."""
        return [c for c in self.camps if c.is_expired()]

    def get_active_camps(self) -> List[ReliefCamp]:
        """Get all active (non-closed, non-expired) camps."""
        return [c for c in self.camps if c.status == "active" and not c.is_expired()]

    def _auto_assign_camp(self) -> Optional[ReliefCamp]:
        available = [c for c in self.camps if c.check_capacity()]
        if not available:
            return None
        return max(available, key=lambda c: (c.max_capacity - c.current_occupancy))

    def register_victim(
        self,
        *,
        victim_id: str,
        name: str,
        age: int,
        address: str,
        health_condition: str,
        injury: str,
    ) -> Victim:
        if any(v.victim_id == victim_id for v in self.victims):
            raise ValueError("Victim ID already exists")
        if not self.camps:
            raise ValueError("No camps available")

        health_condition = health_condition.lower().strip()
        if health_condition not in {"normal", "critical"}:
            raise ValueError("Health condition must be 'normal' or 'critical'")

        address = address.strip()
        injury = injury.strip()
        if not address:
            raise ValueError("Address is required")

        assigned = self._auto_assign_camp()
        if not assigned:
            raise RuntimeError("All camps are full")

        doctor_name: Optional[str] = None
        doctor_specialty: Optional[str] = None
        # Auto-allocate doctor based on injury for all victims (not just critical)
        if injury and self.can_manage_role("doctor"):
            doctor_name, doctor_specialty = self._allocate_doctor(injury)

        victim = Victim(
            victim_id=victim_id,
            name=name,
            age=age,
            address=address,
            health_condition=health_condition,
            injury=injury,
            doctor_name=doctor_name,
            doctor_specialty=doctor_specialty,
            assigned_camp=assigned.camp_id,
        )
        self.victims.append(victim)
        assigned.current_occupancy += 1

        # Persist a "real-world" assignment on the doctor record too.
        if victim.doctor_name:
            doc = self._doctor_responder_by_name(victim.doctor_name)
            if doc:
                doc.assigned_to_type = "victim"
                doc.assigned_to_id = victim.victim_id
                doc.assigned_note = f"Auto allocated for injury: {injury}"
        self.save_data()
        return victim

    def delete_victim(self, *, victim_id: str) -> None:
        """Delete a victim (typically after full recovery). Also frees assigned doctor."""
        victim = self.victim_by_id(victim_id)
        if not victim:
            raise ValueError("Victim not found")

        # Only allow deleting normal (recovered) victims
        if victim.health_condition == "critical":
            raise ValueError("Cannot delete critical victim. Wait until fully recovered.")

        # Free the assigned doctor if any
        if victim.doctor_name:
            doc = self._doctor_responder_by_name(victim.doctor_name)
            if doc and doc.assigned_to_id == victim_id:
                doc.assigned_to_type = None
                doc.assigned_to_id = None
                doc.assigned_note = None
                doc.status = "free"
                doc.assigned_at = None
                doc.estimated_duration_minutes = None
                doc.task_description = None

        # Update camp occupancy
        if victim.assigned_camp:
            camp = self.camp_by_id(victim.assigned_camp)
            if camp and camp.current_occupancy > 0:
                camp.current_occupancy -= 1

        # Remove from list
        self.victims = [v for v in self.victims if v.victim_id != victim_id]
        self.save_data()

    def _injury_to_specialty(self, injury: str) -> str:
        """Map an injury description to a doctor specialty (simple keyword rules)."""

        text = injury.lower()
        if any(k in text for k in ["fracture", "broken", "bone", "sprain", "disloc"]):
            return "Orthopedic"
        if any(k in text for k in ["burn", "scald", "fire"]):
            return "Burn Care"
        if any(k in text for k in ["heart", "chest pain", "cardiac"]):
            return "Cardiology"
        if any(k in text for k in ["head", "brain", "unconscious", "seizure", "stroke"]):
            return "Neurology"
        if any(k in text for k in ["breath", "asthma", "respir", "lungs"]):
            return "Respiratory"
        return "Emergency"

    def _allocate_doctor(self, injury: str) -> tuple[str, str]:
        """Allocate a doctor for a critical victim based on injury.

        Uses a smallest-load rule among doctors with the matching specialty.
        """
        from datetime import datetime

        specialty = self._injury_to_specialty(injury)
        doctors = [r for r in self.responders if r.role == "doctor"]
        eligible = [d for d in doctors if (d.specialty or "") == specialty]
        if not eligible:
            eligible = [d for d in doctors if (d.specialty or "") == "Emergency"]
            specialty = "Emergency"

        # Count current assignments to balance load (victims are the source of truth).
        counts: Dict[str, int] = {}
        for victim in self.victims:
            if victim.doctor_name:
                counts[victim.doctor_name] = counts.get(victim.doctor_name, 0) + 1

        # Prefer free doctors first; then least-loaded.
        def sort_key(doc: Responder) -> tuple[int, int]:
            free_rank = 0 if doc.status == "free" else 1
            return (free_rank, counts.get(doc.name, 0))

        chosen = min(eligible, key=sort_key)

        # Update doctor status for more realistic tracking.
        injury_text = injury.lower()
        operation_keywords = [
            "operation",
            "surgery",
            "amputation",
            "internal bleeding",
            "open fracture",
            "major burn",
        ]
        chosen.status = "in_operation" if any(k in injury_text for k in operation_keywords) else "busy"
        chosen.assigned_at = datetime.now().isoformat()
        chosen.assigned_to_type = "victim"
        # Estimate duration based on status: operations take longer
        if chosen.status == "in_operation":
            chosen.estimated_duration_minutes = 120  # 2 hours for operations
            chosen.task_description = f"Operation for: {injury}"
        else:
            chosen.estimated_duration_minutes = 30  # 30 min for regular treatment
            chosen.task_description = f"Treatment for: {injury}"
        self.save_data()

        return chosen.name, chosen.specialty or specialty

    def update_camp_resources(self, *, camp_id: str, food_add: int, medical_add: int) -> None:
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")
        if food_add < 0 or medical_add < 0:
            raise ValueError("Add values must be 0 or greater")
        camp.update_resources(food_delta=food_add, medical_delta=medical_add)
        self.save_data()

    def distribute_food(self) -> int:
        """Distribute one food packet to each victim if available in their camp."""

        distributed = 0
        for victim in self.victims:
            if victim.food_received or not victim.assigned_camp:
                continue
            camp = self.camp_by_id(victim.assigned_camp)
            if not camp:
                continue
            if camp.available_food_packets > 0:
                camp.update_resources(food_delta=-1)
                victim.food_received = True
                distributed += 1
        self.save_data()
        return distributed

    def distribute_medical(self) -> int:
        """Distribute medical kits with priority to critical victims."""

        def priority(v: Victim) -> int:
            return 0 if v.health_condition == "critical" else 1

        distributed = 0
        for victim in sorted(self.victims, key=priority):
            if victim.medical_received or not victim.assigned_camp:
                continue
            camp = self.camp_by_id(victim.assigned_camp)
            if not camp:
                continue
            if camp.available_medical_kits > 0:
                camp.update_resources(medical_delta=-1)
                victim.medical_received = True
                distributed += 1
        self.save_data()
        return distributed

    # ----------------------------- Analytics -----------------------------
    def report(self) -> Dict[str, object]:
        total_camps = len(self.camps)
        total_victims = len(self.victims)
        critical_victims = sum(1 for v in self.victims if v.health_condition == "critical")

        highest = None
        if self.camps:
            highest = max(self.camps, key=lambda c: c.current_occupancy)

        food_distributed = sum(1 for v in self.victims if v.food_received)
        medical_distributed = sum(1 for v in self.victims if v.medical_received)

        return {
            "total_camps": total_camps,
            "total_victims": total_victims,
            "critical_victims": critical_victims,
            "disaster_type": self.get_disaster_type(),
            "disaster_subtype": self.get_disaster_subtype(),
            "disaster_subtype_label": self.disaster_subtype_label(),
            "highest_camp_id": highest.camp_id if highest else None,
            "highest_occupancy": highest.current_occupancy if highest else 0,
            "highest_capacity": highest.max_capacity if highest else 0,
            "food_distributed": food_distributed,
            "medical_distributed": medical_distributed,
            "doctor_status": self.status_counts(role="doctor"),
        }

    # ----------------------------- Volunteer Management -----------------------------
    def _save_volunteers_to_txt(self) -> None:
        """Save volunteers to text file (volunteers.txt) for file handling requirement."""
        try:
            with open(self.VOLUNTEERS_TXT_FILE, "w", encoding="utf-8") as f:
                f.write("=== Volunteer Registry ===\n\n")
                for v in self.volunteers:
                    f.write(f"Volunteer ID: {v.volunteer_id}\n")
                    f.write(f"Name: {v.name}\n")
                    f.write(f"Assigned Camp: {v.assigned_camp or 'Unassigned'}\n")
                    f.write(f"Task: {v.task or 'No task assigned'}\n")
                    f.write("-" * 40 + "\n")
        except Exception as e:
            print(f"Error writing volunteers.txt: {e}")

    def log_distribution(self, distribution_type: str, camp_id: str, amount: int, details: str = "") -> None:
        """Log distribution events to distribution_log.txt for file handling requirement."""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.DISTRIBUTION_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {distribution_type.upper()} | Camp: {camp_id} | Amount: {amount}")
                if details:
                    f.write(f" | {details}")
                f.write("\n")
        except Exception as e:
            print(f"Error writing distribution_log.txt: {e}")

    def add_volunteer(
        self,
        *,
        volunteer_id: str,
        name: str,
        assigned_camp: Optional[str] = None,
        task: Optional[str] = None
    ) -> Volunteer:
        """Add a new volunteer to the system."""
        if any(v.volunteer_id == volunteer_id for v in self.volunteers):
            raise ValueError("Volunteer ID already exists")
        
        # Validate camp if assigned
        if assigned_camp:
            camp = self.camp_by_id(assigned_camp)
            if not camp:
                raise ValueError("Assigned camp does not exist")
        
        volunteer = Volunteer(
            volunteer_id=volunteer_id,
            name=name,
            assigned_camp=assigned_camp,
            task=task
        )
        self.volunteers.append(volunteer)
        self.save_data()
        return volunteer

    def assign_volunteer_to_camp(self, *, volunteer_id: str, camp_id: str, task: Optional[str] = None) -> Volunteer:
        """Assign a volunteer to a specific camp with optional task."""
        volunteer = self.volunteer_by_id(volunteer_id)
        if not volunteer:
            raise ValueError("Volunteer not found")
        
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")
        
        volunteer.assigned_camp = camp_id
        if task:
            volunteer.task = task
        self.save_data()
        return volunteer

    def volunteer_by_id(self, volunteer_id: str) -> Optional[Volunteer]:
        """Find a volunteer by ID."""
        for v in self.volunteers:
            if v.volunteer_id == volunteer_id:
                return v
        return None

    def get_volunteers_by_camp(self, camp_id: str) -> List[Volunteer]:
        """Get all volunteers assigned to a specific camp."""
        return [v for v in self.volunteers if v.assigned_camp == camp_id]

    def get_all_volunteers(self) -> List[Volunteer]:
        """Get all volunteers."""
        return list(self.volunteers)

    def delete_volunteer(self, *, volunteer_id: str) -> None:
        """Delete a volunteer from the system."""
        volunteer = self.volunteer_by_id(volunteer_id)
        if not volunteer:
            raise ValueError("Volunteer not found")
        self.volunteers = [v for v in self.volunteers if v.volunteer_id != volunteer_id]
        self.save_data()

    # ----------------------------- Victim Health & Transfer -----------------------------
    def update_victim_health(self, *, victim_id: str, health_condition: str) -> Victim:
        """Update a victim's health condition (normal/critical)."""
        victim = self.victim_by_id(victim_id)
        if not victim:
            raise ValueError("Victim not found")
        
        health_condition = health_condition.lower().strip()
        if health_condition not in {"normal", "critical"}:
            raise ValueError("Health condition must be 'normal' or 'critical'")
        
        old_condition = victim.health_condition
        victim.health_condition = health_condition
        
        # If victim becomes critical and has an injury but no doctor, try to allocate
        if health_condition == "critical" and old_condition != "critical":
            if victim.injury and not victim.doctor_name and self.can_manage_role("doctor"):
                doctor_name, doctor_specialty = self._allocate_doctor(victim.injury)
                victim.doctor_name = doctor_name
                victim.doctor_specialty = doctor_specialty
                # Update doctor record
                doc = self._doctor_responder_by_name(victim.doctor_name)
                if doc:
                    doc.assigned_to_type = "victim"
                    doc.assigned_to_id = victim.victim_id
                    doc.assigned_note = f"Auto allocated for injury: {victim.injury}"
        
        # If victim recovers from critical, free the doctor
        if health_condition == "normal" and old_condition == "critical" and victim.doctor_name:
            doc = self._doctor_responder_by_name(victim.doctor_name)
            if doc and doc.assigned_to_id == victim_id:
                doc.assigned_to_type = None
                doc.assigned_to_id = None
                doc.assigned_note = None
                doc.status = "free"
                doc.assigned_at = None
                doc.estimated_duration_minutes = None
                doc.task_description = None
            victim.doctor_name = None
            victim.doctor_specialty = None
        
        self.save_data()
        return victim

    def transfer_victim(self, *, victim_id: str, target_camp_id: str) -> Victim:
        """Transfer a victim from their current camp to another camp."""
        victim = self.victim_by_id(victim_id)
        if not victim:
            raise ValueError("Victim not found")
        
        if victim.assigned_camp == target_camp_id:
            raise ValueError("Victim is already in this camp")
        
        target_camp = self.camp_by_id(target_camp_id)
        if not target_camp:
            raise ValueError("Target camp not found")
        
        if not target_camp.check_capacity():
            raise ValueError(f"Target camp '{target_camp.camp_id}' is at full capacity")
        
        # Update source camp occupancy
        if victim.assigned_camp:
            source_camp = self.camp_by_id(victim.assigned_camp)
            if source_camp and source_camp.current_occupancy > 0:
                source_camp.current_occupancy -= 1
        
        # Update target camp occupancy
        target_camp.current_occupancy += 1
        
        # Update victim assignment
        old_camp = victim.assigned_camp
        victim.assigned_camp = target_camp_id
        
        # Log the transfer
        self.log_distribution("TRANSFER", target_camp_id, 1, f"Victim {victim_id} transferred from {old_camp or 'N/A'}")
        
        self.save_data()
        return victim

    # ----------------------------- Camp Occupancy & Alerts -----------------------------
    def get_camp_occupancy_percentage(self, camp_id: str) -> float:
        """Calculate occupancy percentage for a specific camp."""
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")
        
        if camp.max_capacity == 0:
            return 0.0
        
        return (camp.current_occupancy / camp.max_capacity) * 100

    def get_all_camps_occupancy(self) -> List[Dict[str, object]]:
        """Get occupancy percentage for all camps."""
        result = []
        for camp in self.camps:
            if camp.max_capacity > 0:
                percentage = (camp.current_occupancy / camp.max_capacity) * 100
            else:
                percentage = 0.0
            result.append({
                "camp_id": camp.camp_id,
                "location": camp.location,
                "current_occupancy": camp.current_occupancy,
                "max_capacity": camp.max_capacity,
                "occupancy_percentage": round(percentage, 2),
                "status": camp.status
            })
        return result

    def get_high_occupancy_alerts(self, threshold: float = 90.0) -> List[Dict[str, object]]:
        """Get camps with occupancy at or above the threshold (default 90%).
        
        This is the Emergency Alert System for camps reaching critical capacity.
        """
        alerts = []
        for camp in self.camps:
            if camp.max_capacity == 0:
                continue
            
            percentage = (camp.current_occupancy / camp.max_capacity) * 100
            if percentage >= threshold:
                alerts.append({
                    "camp_id": camp.camp_id,
                    "location": camp.location,
                    "current_occupancy": camp.current_occupancy,
                    "max_capacity": camp.max_capacity,
                    "occupancy_percentage": round(percentage, 2),
                    "alert_level": "CRITICAL" if percentage >= 95 else "WARNING",
                    "remaining_capacity": camp.max_capacity - camp.current_occupancy
                })
        
        # Sort by occupancy percentage descending
        alerts.sort(key=lambda x: x["occupancy_percentage"], reverse=True)
        return alerts

    # ----------------------------- Disaster Tracking & Management -----------------------------
    def create_disaster(
        self,
        *,
        disaster_type: str,
        location: str,
        disaster_subtype: Optional[str] = None,
        severity: str = "medium",
        reported_by: Optional[str] = None,
        description: Optional[str] = None,
        affected_area: Optional[str] = None,
        estimated_victims: int = 0,
        request_id: Optional[str] = None,
        proof_image: Optional[str] = None,
    ) -> ActiveDisaster:
        """Create and track a new active disaster."""
        import uuid
        from datetime import datetime

        disaster_id = f"DIS-{uuid.uuid4().hex[:8].upper()}"
        
        disaster = ActiveDisaster(
            disaster_id=disaster_id,
            disaster_type=disaster_type.lower().strip(),
            disaster_subtype=disaster_subtype,
            location=location.strip(),
            severity=severity.lower().strip(),
            status="ongoing",
            reported_at=datetime.now().isoformat(),
            approved_at=datetime.now().isoformat(),
            reported_by=reported_by,
            description=description,
            affected_area=affected_area,
            estimated_victims=estimated_victims,
            request_id=request_id,
            proof_image=proof_image,
        )
        
        disaster.add_update(f"Disaster reported at {location}", reported_by or "System")
        disaster.add_update("Disaster verified and response initiated", "Admin")
        
        self.active_disasters.append(disaster)
        self.save_data()
        return disaster

    def disaster_by_id(self, disaster_id: str) -> Optional[ActiveDisaster]:
        """Find a disaster by ID."""
        for d in self.active_disasters:
            if d.disaster_id == disaster_id:
                return d
        return None

    def get_active_disasters(self) -> List[ActiveDisaster]:
        """Get all non-resolved disasters."""
        return [d for d in self.active_disasters if d.status not in {"resolved", "closed"}]

    def get_all_disasters(self) -> List[ActiveDisaster]:
        """Get all disasters (including resolved)."""
        return list(self.active_disasters)

    def update_disaster_status(
        self,
        *,
        disaster_id: str,
        status: str,
        update_message: Optional[str] = None,
        updated_by: str = "Admin",
    ) -> ActiveDisaster:
        """Update the status of a disaster."""
        from datetime import datetime

        disaster = self.disaster_by_id(disaster_id)
        if not disaster:
            raise ValueError("Disaster not found")
        
        status = status.lower().strip()
        if status not in DISASTER_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(DISASTER_STATUSES)}")
        
        old_status = disaster.status
        disaster.status = status
        
        # Set resolved timestamp if resolving/closing
        if status in {"resolved", "closed"} and old_status not in {"resolved", "closed"}:
            disaster.resolved_at = datetime.now().isoformat()
            # Free all assigned responders
            for rid in disaster.assigned_responders:
                responder = self.responder_by_id(rid)
                if responder and responder.status != "free":
                    responder.status = "free"
                    responder.assigned_to_type = None
                    responder.assigned_to_id = None
                    responder.assigned_note = None
                    responder.assigned_at = None
                    responder.estimated_duration_minutes = None
                    responder.task_description = None
        
        # Add update message
        default_messages = {
            "ongoing": f"Status changed to ongoing from {old_status}",
            "contained": "Disaster has been contained. Situation under control.",
            "resolved": "Disaster resolved. All teams recalled.",
            "closed": "Disaster incident closed.",
        }
        message = update_message or default_messages.get(status, f"Status updated to {status}")
        disaster.add_update(message, updated_by)
        
        self.save_data()
        return disaster

    def add_disaster_update(
        self,
        *,
        disaster_id: str,
        message: str,
        updated_by: str = "Admin",
    ) -> ActiveDisaster:
        """Add a status update/note to a disaster."""
        disaster = self.disaster_by_id(disaster_id)
        if not disaster:
            raise ValueError("Disaster not found")
        
        disaster.add_update(message, updated_by)
        self.save_data()
        return disaster

    def assign_responder_to_disaster(
        self,
        *,
        disaster_id: str,
        responder_id: str,
        task_description: Optional[str] = None,
    ) -> ActiveDisaster:
        """Assign a responder to a disaster."""
        from datetime import datetime

        disaster = self.disaster_by_id(disaster_id)
        if not disaster:
            raise ValueError("Disaster not found")
        
        responder = self.responder_by_id(responder_id)
        if not responder:
            raise ValueError("Responder not found")
        
        if responder_id not in disaster.assigned_responders:
            disaster.assigned_responders.append(responder_id)
        
        # Update responder status
        responder.status = "busy"
        responder.assigned_to_type = "disaster"
        responder.assigned_to_id = disaster_id
        responder.assigned_note = f"Assigned to {disaster.disaster_type} at {disaster.location}"
        responder.assigned_at = datetime.now().isoformat()
        responder.task_description = task_description or f"Disaster response: {disaster.disaster_type}"
        
        disaster.add_update(f"Responder {responder.name} ({responder.role}) assigned", "Admin")
        
        self.save_data()
        return disaster

    def unassign_responder_from_disaster(
        self,
        *,
        disaster_id: str,
        responder_id: str,
    ) -> ActiveDisaster:
        """Remove a responder from a disaster and free them."""
        disaster = self.disaster_by_id(disaster_id)
        if not disaster:
            raise ValueError("Disaster not found")
        
        responder = self.responder_by_id(responder_id)
        if not responder:
            raise ValueError("Responder not found")
        
        if responder_id in disaster.assigned_responders:
            disaster.assigned_responders.remove(responder_id)
        
        # Free the responder
        responder.status = "free"
        responder.assigned_to_type = None
        responder.assigned_to_id = None
        responder.assigned_note = None
        responder.assigned_at = None
        responder.estimated_duration_minutes = None
        responder.task_description = None
        
        disaster.add_update(f"Responder {responder.name} ({responder.role}) unassigned and freed", "Admin")
        
        self.save_data()
        return disaster

    def assign_camp_to_disaster(self, *, disaster_id: str, camp_id: str) -> ActiveDisaster:
        """Link a relief camp to a disaster for coordination."""
        disaster = self.disaster_by_id(disaster_id)
        if not disaster:
            raise ValueError("Disaster not found")
        
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")
        
        if camp_id not in disaster.assigned_camps:
            disaster.assigned_camps.append(camp_id)
            disaster.add_update(f"Camp {camp_id} ({camp.location}) assigned for relief operations", "Admin")
        
        self.save_data()
        return disaster

    def get_disaster_summary(self, disaster_id: str) -> Dict[str, object]:
        """Get a detailed summary of a disaster including responders and camps."""
        disaster = self.disaster_by_id(disaster_id)
        if not disaster:
            raise ValueError("Disaster not found")
        
        # Get assigned responders details
        responder_details = []
        for rid in disaster.assigned_responders:
            responder = self.responder_by_id(rid)
            if responder:
                responder_details.append({
                    "responder_id": responder.responder_id,
                    "name": responder.name,
                    "role": responder.role,
                    "specialty": responder.specialty,
                    "status": responder.status,
                    "task": responder.task_description,
                })
        
        # Get assigned camps details
        camp_details = []
        for cid in disaster.assigned_camps:
            camp = self.camp_by_id(cid)
            if camp:
                camp_details.append({
                    "camp_id": camp.camp_id,
                    "location": camp.location,
                    "current_occupancy": camp.current_occupancy,
                    "max_capacity": camp.max_capacity,
                    "status": camp.status,
                })
        
        return {
            "disaster": disaster.to_dict(),
            "responders": responder_details,
            "camps": camp_details,
            "total_responders": len(responder_details),
            "total_camps": len(camp_details),
        }

    # ----------------------------- Broadcast Alert -----------------------------
    def get_broadcast_alert(self) -> Optional[Dict[str, str]]:
        """Return current broadcast alert or None."""
        alert = self.settings.get("broadcast_alert")
        return alert if isinstance(alert, dict) and alert.get("message") else None

    def set_broadcast_alert(self, message: str, set_by: str = "Admin", severity: str = "info") -> None:
        """Post a broadcast alert visible on HelpDesk."""
        from datetime import datetime
        self.settings["broadcast_alert"] = {
            "message": str(message).strip(),
            "severity": severity,
            "set_by": set_by,
            "set_at": datetime.now().isoformat(),
        }
        self.save_data()

    def clear_broadcast_alert(self) -> None:
        """Remove the broadcast alert."""
        self.settings.pop("broadcast_alert", None)
        self.save_data()

    # ----------------------------- Camp Closure -----------------------------
    def close_camp(self, camp_id: str) -> ReliefCamp:
        """Manually close a camp."""
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")
        camp.status = "closed"
        self.save_data()
        return camp

    def reopen_camp(self, camp_id: str) -> ReliefCamp:
        """Reopen a closed camp."""
        camp = self.camp_by_id(camp_id)
        if not camp:
            raise ValueError("Camp not found")
        camp.status = "active"
        self.save_data()
        return camp

    def auto_close_expired_camps(self) -> int:
        """Close all camps that are past their deadline. Returns count closed."""
        count = 0
        for camp in self.camps:
            if camp.status == "active" and camp.is_expired():
                camp.status = "closed"
                count += 1
        if count:
            self.save_data()
        return count

    # ----------------------------- Missing Persons -----------------------------
    MISSING_FILE = _data_file_path("missing_persons.json")

    def _load_missing(self) -> list:
        return safe_load_json(self.MISSING_FILE, default=[])

    def _save_missing(self, records: list) -> None:
        safe_write_json(self.MISSING_FILE, records)

    def report_missing_person(
        self,
        *,
        name: str,
        age: int = None,
        description: str = "",
        last_seen: str = "",
        reported_by: str = "",
    ) -> Dict[str, object]:
        """Register a missing person report."""
        import uuid
        from datetime import datetime
        records = self._load_missing()
        record = {
            "id": str(uuid.uuid4()),
            "name": str(name).strip(),
            "age": int(age) if age is not None else None,
            "description": str(description).strip(),
            "last_seen": str(last_seen).strip(),
            "reported_by": str(reported_by).strip(),
            "status": "missing",
            "reported_at": datetime.now().isoformat(),
            "found_at": None,
            "found_note": None,
        }
        records.append(record)
        self._save_missing(records)
        return record

    def search_missing_persons(self, query: str) -> list:
        """Search missing persons by name or last seen location (case-insensitive)."""
        q = str(query).strip().lower()
        records = self._load_missing()
        if not q:
            return records
        return [
            r for r in records
            if q in r.get("name", "").lower()
            or q in r.get("last_seen", "").lower()
        ]

    def mark_person_found(self, record_id: str, found_note: str = None) -> Dict[str, object]:
        """Mark a missing person as found."""
        from datetime import datetime
        records = self._load_missing()
        result = None
        for r in records:
            if r.get("id") == record_id:
                r["status"] = "found"
                r["found_at"] = datetime.now().isoformat()
                r["found_note"] = found_note
                result = r
                break
        self._save_missing(records)
        return result

    def get_all_missing_persons(self) -> list:
        return self._load_missing()

    # ----------------------------- Resource Needs Tracker -----------------------------
    def add_resource_need(
        self,
        *,
        disaster_id: str,
        item: str,
        quantity: int = 1,
        priority: str = "normal",
        note: str = "",
    ) -> "ActiveDisaster":
        """Add an outstanding resource need to a disaster."""
        from datetime import datetime
        disaster = self.disaster_by_id(disaster_id)
        if not disaster:
            raise ValueError("Disaster not found")
        if not hasattr(disaster, "resource_needs") or disaster.resource_needs is None:
            disaster.resource_needs = []
        disaster.resource_needs.append({
            "id": __import__("uuid").uuid4().hex[:8],
            "item": str(item).strip(),
            "quantity": int(quantity),
            "priority": str(priority).strip(),
            "note": str(note).strip(),
            "status": "needed",
            "added_at": datetime.now().isoformat(),
            "fulfilled_at": None,
        })
        self.save_data()
        return disaster

    def fulfill_resource_need(self, *, disaster_id: str, need_id: str) -> "ActiveDisaster":
        """Mark a resource need as fulfilled."""
        from datetime import datetime
        disaster = self.disaster_by_id(disaster_id)
        if not disaster:
            raise ValueError("Disaster not found")
        for need in (disaster.resource_needs or []):
            if need.get("id") == need_id:
                need["status"] = "fulfilled"
                need["fulfilled_at"] = datetime.now().isoformat()
                break
        self.save_data()
        return disaster
