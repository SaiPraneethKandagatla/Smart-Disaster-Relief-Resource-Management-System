"""Smart Disaster Relief Resource Management System

University-level Python OOP mini project.

Features:
- Manage relief camps and victims (OOP with classes + constructors)
- Persist data to JSON files (camps + victims)
- Automatically assign victims to camps based on capacity
- Distribute resources with rules (food for all if available; medical prioritized for critical)
- Search and reporting (basic data analysis)
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional


def _data_dir() -> str:
	"""Return the directory where persistent JSON data should be stored.

	If this script is run from a subfolder (e.g., `project/project.py`) but the
	parent folder already contains `camps.json`/`victims.json`, we reuse the
	parent so data stays consistent.
	"""

	script_dir = os.path.dirname(os.path.abspath(__file__))
	parent_dir = os.path.dirname(script_dir)

	script_has_data = (
		os.path.exists(os.path.join(script_dir, "camps.json"))
		or os.path.exists(os.path.join(script_dir, "victims.json"))
	)
	parent_has_data = (
		os.path.exists(os.path.join(parent_dir, "camps.json"))
		or os.path.exists(os.path.join(parent_dir, "victims.json"))
	)

	if parent_has_data and not script_has_data:
		return parent_dir
	return script_dir


def _data_file_path(filename: str) -> str:
	"""Return an absolute path for a persistent data file."""

	return os.path.join(_data_dir(), filename)


def _safe_load_json(path: str, default):
	"""Load JSON from path, returning default if file doesn't exist or is invalid."""

	if not os.path.exists(path):
		return default
	try:
		with open(path, "r", encoding="utf-8") as file:
			return json.load(file)
	except (json.JSONDecodeError, OSError):
		return default


def _safe_write_json(path: str, data) -> None:
	"""Write JSON safely to path."""

	with open(path, "w", encoding="utf-8") as file:
		json.dump(data, file, indent=2)


def _input_non_empty(prompt: str) -> str:
	"""Read a non-empty string from user."""

	while True:
		value = input(prompt).strip()
		if value:
			return value
		print("Input cannot be empty. Please try again.")


def _input_int(prompt: str, *, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
	"""Read an integer with basic validation."""

	while True:
		raw = input(prompt).strip()
		try:
			value = int(raw)
		except ValueError:
			print("Please enter a valid integer.")
			continue

		if min_value is not None and value < min_value:
			print(f"Value must be at least {min_value}.")
			continue
		if max_value is not None and value > max_value:
			print(f"Value must be at most {max_value}.")
			continue
		return value


def _input_choice(prompt: str, choices: List[str]) -> str:
	"""Read a choice from a list (case-insensitive). Returns a normalized value."""

	normalized = {c.lower(): c for c in choices}
	while True:
		raw = input(prompt).strip().lower()
		if raw in normalized:
			return normalized[raw]
		print(f"Invalid choice. Choose one of: {', '.join(choices)}")


class ReliefCamp:
	"""Represents a relief camp and its resources."""

	def __init__(
		self,
		camp_id: str,
		location: str,
		max_capacity: int,
		current_occupancy: int,
		available_food_packets: int,
		available_medical_kits: int,
		volunteers: List[str],
	):
		self.camp_id = camp_id
		self.location = location
		self.max_capacity = max_capacity
		self.current_occupancy = current_occupancy
		self.available_food_packets = available_food_packets
		self.available_medical_kits = available_medical_kits
		self.volunteers = volunteers

	@classmethod
	def add_camp(cls, existing_ids: set[str]) -> "ReliefCamp":
		"""Create a new camp object from interactive user input."""

		while True:
			camp_id = _input_non_empty("Enter Camp ID: ")
			if camp_id in existing_ids:
				print("Camp ID already exists. Enter a unique Camp ID.")
			else:
				break

		location = _input_non_empty("Enter Location: ")
		max_capacity = _input_int("Enter Max Capacity: ", min_value=1)
		available_food_packets = _input_int("Enter Available Food Packets: ", min_value=0)
		available_medical_kits = _input_int("Enter Available Medical Kits: ", min_value=0)
		volunteer_text = input("Enter Volunteers (comma-separated, optional): ").strip()
		volunteers = [v.strip() for v in volunteer_text.split(",") if v.strip()]

		return cls(
			camp_id=camp_id,
			location=location,
			max_capacity=max_capacity,
			current_occupancy=0,
			available_food_packets=available_food_packets,
			available_medical_kits=available_medical_kits,
			volunteers=volunteers,
		)

	def check_capacity(self) -> bool:
		"""Return True if camp can accept more victims."""

		return self.current_occupancy < self.max_capacity

	def update_resources(self, *, food_delta: int = 0, medical_delta: int = 0) -> None:
		"""Update resource quantities (positive adds, negative subtracts)."""

		self.available_food_packets = max(0, self.available_food_packets + food_delta)
		self.available_medical_kits = max(0, self.available_medical_kits + medical_delta)

	def display_camp_details(self) -> None:
		"""Print camp details to console."""

		print("\n--- Camp Details ---")
		print(f"Camp ID            : {self.camp_id}")
		print(f"Location           : {self.location}")
		print(f"Capacity           : {self.current_occupancy}/{self.max_capacity}")
		print(f"Food Packets       : {self.available_food_packets}")
		print(f"Medical Kits       : {self.available_medical_kits}")
		print(f"Volunteers         : {', '.join(self.volunteers) if self.volunteers else 'None'}")

	def to_dict(self) -> Dict:
		return {
			"camp_id": self.camp_id,
			"location": self.location,
			"max_capacity": self.max_capacity,
			"current_occupancy": self.current_occupancy,
			"available_food_packets": self.available_food_packets,
			"available_medical_kits": self.available_medical_kits,
			"volunteers": self.volunteers,
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
		)


class Victim:
	"""Represents a disaster victim."""

	def __init__(
		self,
		victim_id: str,
		name: str,
		age: int,
		health_condition: str,  # "normal" or "critical"
		assigned_camp: Optional[str],
		food_received: bool = False,
		medical_received: bool = False,
	):
		self.victim_id = victim_id
		self.name = name
		self.age = age
		self.health_condition = health_condition
		self.assigned_camp = assigned_camp
		self.food_received = food_received
		self.medical_received = medical_received

	@classmethod
	def register_victim(cls, existing_ids: set[str]) -> "Victim":
		"""Create a new victim object from interactive user input."""

		while True:
			victim_id = _input_non_empty("Enter Victim ID: ")
			if victim_id in existing_ids:
				print("Victim ID already exists. Enter a unique Victim ID.")
			else:
				break

		name = _input_non_empty("Enter Name: ")
		age = _input_int("Enter Age: ", min_value=0, max_value=120)
		health_condition = _input_choice("Health Condition (normal/critical): ", ["normal", "critical"]).lower()

		# assigned_camp will be set by the system during auto-assignment
		return cls(
			victim_id=victim_id,
			name=name,
			age=age,
			health_condition=health_condition,
			assigned_camp=None,
		)

	def display_victim(self) -> None:
		"""Print victim details to console."""

		print("\n--- Victim Details ---")
		print(f"Victim ID          : {self.victim_id}")
		print(f"Name               : {self.name}")
		print(f"Age                : {self.age}")
		print(f"Health Condition   : {self.health_condition}")
		print(f"Assigned Camp      : {self.assigned_camp if self.assigned_camp else 'Not Assigned'}")
		print(f"Food Received      : {'Yes' if self.food_received else 'No'}")
		print(f"Medical Kit Received: {'Yes' if self.medical_received else 'No'}")

	def to_dict(self) -> Dict:
		return {
			"victim_id": self.victim_id,
			"name": self.name,
			"age": self.age,
			"health_condition": self.health_condition,
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
			health_condition=str(data.get("health_condition", "normal")).lower(),
			assigned_camp=data.get("assigned_camp"),
			food_received=bool(data.get("food_received", False)),
			medical_received=bool(data.get("medical_received", False)),
		)


class DisasterReliefSystem:
	"""Main application controller (stores data, runs menu, performs operations)."""

	CAMPS_FILE = _data_file_path("camps.json")
	VICTIMS_FILE = _data_file_path("victims.json")

	def __init__(self) -> None:
		self.camps: List[ReliefCamp] = []
		self.victims: List[Victim] = []
		self.load_data()

	# ----------------------------- Persistence -----------------------------
	def load_data(self) -> None:
		"""Load camps and victims from JSON files."""

		camps_data = _safe_load_json(self.CAMPS_FILE, default=[])
		victims_data = _safe_load_json(self.VICTIMS_FILE, default=[])

		self.camps = [ReliefCamp.from_dict(item) for item in camps_data if isinstance(item, dict)]
		self.victims = [Victim.from_dict(item) for item in victims_data if isinstance(item, dict)]

		# Ensure occupancies match the number of assigned victims.
		self._recompute_occupancies()

	def save_data(self) -> None:
		"""Save camps and victims to JSON files."""

		_safe_write_json(self.CAMPS_FILE, [c.to_dict() for c in self.camps])
		_safe_write_json(self.VICTIMS_FILE, [v.to_dict() for v in self.victims])

	def _recompute_occupancies(self) -> None:
		"""Recalculate camp occupancies from victim assignments (basic consistency check)."""

		counts: Dict[str, int] = {}
		for victim in self.victims:
			if victim.assigned_camp:
				counts[victim.assigned_camp] = counts.get(victim.assigned_camp, 0) + 1

		for camp in self.camps:
			camp.current_occupancy = counts.get(camp.camp_id, 0)

	# ----------------------------- Lookups -----------------------------
	def _camp_by_id(self, camp_id: str) -> Optional[ReliefCamp]:
		for camp in self.camps:
			if camp.camp_id == camp_id:
				return camp
		return None

	def _victim_by_id(self, victim_id: str) -> Optional[Victim]:
		for victim in self.victims:
			if victim.victim_id == victim_id:
				return victim
		return None

	# ----------------------------- Core Operations -----------------------------
	def add_new_camp(self) -> None:
		existing_ids = {c.camp_id for c in self.camps}
		camp = ReliefCamp.add_camp(existing_ids)
		self.camps.append(camp)
		self.save_data()
		print("\nCamp added successfully.")

	def _auto_assign_camp(self) -> Optional[ReliefCamp]:
		"""Pick a camp with available capacity. Returns None if all are full."""

		# Simple policy: choose the camp with the most remaining capacity.
		available = [c for c in self.camps if c.check_capacity()]
		if not available:
			return None
		return max(available, key=lambda c: (c.max_capacity - c.current_occupancy))

	def register_new_victim(self) -> None:
		if not self.camps:
			print("\nNo camps available. Add a relief camp first.")
			return

		existing_ids = {v.victim_id for v in self.victims}
		victim = Victim.register_victim(existing_ids)

		assigned = self._auto_assign_camp()
		if not assigned:
			print("\nAll camps are full. Victim could not be assigned.")
			return

		victim.assigned_camp = assigned.camp_id
		assigned.current_occupancy += 1
		self.victims.append(victim)

		# Optional: distribute at registration? Requirement says admin can distribute.
		# We'll keep distribution as explicit menu actions.
		self.save_data()
		print(f"\nVictim registered and assigned to Camp {assigned.camp_id}.")

	def distribute_food_packets(self) -> None:
		"""Distribute one food packet per victim if available in their camp."""

		if not self.victims:
			print("\nNo victims registered.")
			return

		distributed = 0
		for victim in self.victims:
			if victim.food_received:
				continue
			if not victim.assigned_camp:
				continue

			camp = self._camp_by_id(victim.assigned_camp)
			if not camp:
				continue

			if camp.available_food_packets > 0:
				camp.update_resources(food_delta=-1)
				victim.food_received = True
				distributed += 1

		self.save_data()
		print(f"\nFood distribution complete. Packets distributed: {distributed}")

	def distribute_medical_kits(self) -> None:
		"""Distribute medical kits, prioritizing critical victims first."""

		if not self.victims:
			print("\nNo victims registered.")
			return

		# Prioritize critical victims, then normal victims
		def priority_key(v: Victim) -> int:
			return 0 if v.health_condition == "critical" else 1

		distributed = 0
		for victim in sorted(self.victims, key=priority_key):
			if victim.medical_received:
				continue
			if not victim.assigned_camp:
				continue

			camp = self._camp_by_id(victim.assigned_camp)
			if not camp:
				continue

			if camp.available_medical_kits > 0:
				camp.update_resources(medical_delta=-1)
				victim.medical_received = True
				distributed += 1

		self.save_data()
		print(f"\nMedical kit distribution complete. Kits distributed: {distributed}")

	def search_victim(self) -> None:
		victim_id = _input_non_empty("Enter Victim ID to search: ")
		victim = self._victim_by_id(victim_id)
		if not victim:
			print("\nVictim not found.")
			return
		victim.display_victim()

	def view_all_camps(self) -> None:
		if not self.camps:
			print("\nNo camps found.")
			return

		print("\n====== All Relief Camps ======")
		for camp in self.camps:
			camp.display_camp_details()

	def view_all_victims(self) -> None:
		if not self.victims:
			print("\nNo victims found.")
			return

		print("\n====== All Victims ======")
		for victim in self.victims:
			victim.display_victim()

	def update_camp_resources(self) -> None:
		"""Add resources to a camp (admin operation)."""

		if not self.camps:
			print("\nNo camps available.")
			return

		camp_id = _input_non_empty("Enter Camp ID to update resources: ")
		camp = self._camp_by_id(camp_id)
		if not camp:
			print("\nCamp not found.")
			return

		food_add = _input_int("Enter food packets to add (0 or more): ", min_value=0)
		medical_add = _input_int("Enter medical kits to add (0 or more): ", min_value=0)
		camp.update_resources(food_delta=food_add, medical_delta=medical_add)
		self.save_data()
		print("\nResources updated successfully.")

	# ----------------------------- Analytics -----------------------------
	def generate_analytical_report(self) -> None:
		"""Print required analytical report."""

		total_camps = len(self.camps)
		total_victims = len(self.victims)
		critical_victims = sum(1 for v in self.victims if v.health_condition == "critical")

		# Camp with highest occupancy
		highest = None
		if self.camps:
			highest = max(self.camps, key=lambda c: c.current_occupancy)

		# Totals distributed derived from victim records (data analysis)
		food_distributed = sum(1 for v in self.victims if v.food_received)
		medical_distributed = sum(1 for v in self.victims if v.medical_received)

		print("\n========== Analytical Report ==========")
		print(f"Total number of camps          : {total_camps}")
		print(f"Total victims registered       : {total_victims}")
		if highest:
			print(
				"Camp with highest occupancy     : "
				f"{highest.camp_id} ({highest.current_occupancy}/{highest.max_capacity})"
			)
		else:
			print("Camp with highest occupancy     : N/A")
		print(f"Total food packets distributed : {food_distributed}")
		print(f"Total medical kits distributed : {medical_distributed}")
		print(f"Number of critical victims     : {critical_victims}")

	# ----------------------------- Menu -----------------------------
	def run(self) -> None:
		"""Run the menu-driven system."""

		while True:
			print("\n\n===== Smart Disaster Relief Resource Management System =====")
			print("1. Add new relief camp")
			print("2. Register disaster victim (auto-assign camp)")
			print("3. Distribute food packets")
			print("4. Distribute medical kits (critical first)")
			print("5. Search victim by ID")
			print("6. View all camps")
			print("7. View all victims")
			print("8. Update camp resources")
			print("9. Generate analytical report")
			print("0. Exit")

			choice = input("Enter your choice: ").strip()

			if choice == "1":
				self.add_new_camp()
			elif choice == "2":
				self.register_new_victim()
			elif choice == "3":
				self.distribute_food_packets()
			elif choice == "4":
				self.distribute_medical_kits()
			elif choice == "5":
				self.search_victim()
			elif choice == "6":
				self.view_all_camps()
			elif choice == "7":
				self.view_all_victims()
			elif choice == "8":
				self.update_camp_resources()
			elif choice == "9":
				self.generate_analytical_report()
			elif choice == "0":
				print("Exiting... Data saved.")
				self.save_data()
				break
			else:
				print("Invalid option. Please try again.")


def main() -> None:
	"""Program entry point."""

	system = DisasterReliefSystem()
	system.run()


if __name__ == "__main__":
	main()

