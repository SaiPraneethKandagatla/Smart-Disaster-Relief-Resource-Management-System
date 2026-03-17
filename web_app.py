"""Web dashboard for Smart Disaster Relief Resource Management System.

UI requirement:
- Forms must open only when clicking buttons (separate pages).

Pages:
- /                Dashboard (report + tables + distribute buttons)
- /camps/new       Add camp form
- /victims/new     Register victim form (includes address + injury)
- /resources/new   Update resources form
- /victims/search  Search victim page

Run:
    python web_app.py
Then open:
    http://127.0.0.1:5000

Admin portal (separate app):
    python admin_app.py
    http://127.0.0.1:5001
"""
from __future__ import annotations

import os
import uuid

from flask import Flask, redirect, render_template, request, url_for, flash
from werkzeug.utils import secure_filename

from relief_system import DisasterReliefSystem
from request_queue import create_request


app = Flask(__name__)
app.secret_key = "aiac-relief-system"  # simple secret for local demo

ALLOWED_PROOF_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
PROOF_UPLOAD_FOLDER = os.path.join(app.static_folder or "static", "disaster_proofs")


def _is_allowed_proof_file(filename: str) -> bool:
    """Return True if file extension is one of allowed proof image types."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_PROOF_EXTENSIONS


@app.context_processor
def _inject_globals():
    # Used by templates (navigation + setup locking UI)
    system = DisasterReliefSystem()
    alert = system.get_broadcast_alert()
    return {
        "setup_locked": bool(system.get_disaster_type()),
        "get_broadcast_alert": lambda: alert,
        "broadcast_alert": alert,
    }


def _system() -> DisasterReliefSystem:
    # Create a fresh instance per request so it always reads latest JSON.
    return DisasterReliefSystem()


def _to_int(value: str, *, min_value: int | None = None) -> int:
    number = int(value)
    if min_value is not None and number < min_value:
        raise ValueError(f"Must be >= {min_value}")
    return number


@app.get("/")
def dashboard():
    system = _system()

    if not system.get_disaster_type():
        return redirect(url_for("setup"))

    return render_template(
        "dashboard.html",
        camps=system.camps,
        report=system.report(),
        activated_roles=system.activated_roles_for_disaster(),
        emergency_contacts=system.get_emergency_contacts(),
        responder_counts={
            "doctor": system.status_counts(role="doctor"),
            "fire_force": system.status_counts(role="fire_force"),
            "police": system.status_counts(role="police"),
            "diver": system.status_counts(role="diver"),
            "ambulance": system.status_counts(role="ambulance"),
        },
    )


@app.get("/setup")
def setup():
    system = _system()
    locked = bool(system.get_disaster_type())
    return render_template(
        "setup.html",
        disaster_type=system.get_disaster_type(),
        disaster_subtype=system.get_disaster_subtype(),
        man_made_disasters=system.list_disaster_subtypes("man_made"),
        natural_disasters=system.list_disaster_subtypes("natural"),
        locked=locked,
    )


@app.post("/setup")
def setup_save():
    system = _system()

    try:
        dtype = request.form.get("disaster_type", "").strip().lower()
        subtype = request.form.get("disaster_subtype", "").strip()
        location = request.form.get("location", "").strip()
        proof_file = request.files.get("proof_image")

        if not dtype or not subtype or not location:
            flash("Please fill all fields: disaster type, specific disaster, and location.", "err")
            return redirect(url_for("dashboard"))

        if not proof_file or not proof_file.filename:
            flash("Please upload a disaster proof photo before submitting.", "err")
            return redirect(url_for("dashboard"))

        if not _is_allowed_proof_file(proof_file.filename):
            flash("Proof image must be PNG, JPG, JPEG, or WEBP.", "err")
            return redirect(url_for("dashboard"))

        os.makedirs(PROOF_UPLOAD_FOLDER, exist_ok=True)
        original_name = secure_filename(proof_file.filename)
        ext = original_name.rsplit(".", 1)[1].lower()
        saved_name = f"proof_{uuid.uuid4().hex}.{ext}"
        save_path = os.path.join(PROOF_UPLOAD_FOLDER, saved_name)
        proof_file.save(save_path)
        proof_image = f"disaster_proofs/{saved_name}"

        create_request(
            kind="disaster_report",
            payload={
                "disaster_type": dtype,
                "disaster_subtype": subtype,
                "location": location,
                "proof_image": proof_image,
            },
        )
        flash("Disaster report submitted. Admin will verify and dispatch teams.", "ok")
        return redirect(url_for("dashboard"))
    except Exception as exc:
        flash(f"Could not submit disaster report: {exc}", "err")
        return redirect(url_for("dashboard"))


@app.get("/camps/new")
def new_camp():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    return render_template("camp_form.html")


@app.post("/camps/add")
def add_camp():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    try:
        camp_id = request.form.get("camp_id", "").strip()
        location = request.form.get("location", "").strip()
        max_capacity = _to_int(request.form.get("max_capacity", "0"), min_value=1)
        food = _to_int(request.form.get("available_food_packets", "0"), min_value=0)
        medical = _to_int(request.form.get("available_medical_kits", "0"), min_value=0)
        volunteers_raw = request.form.get("volunteers", "").strip()
        volunteers = [v.strip() for v in volunteers_raw.split(",") if v.strip()]

        if not camp_id or not location:
            raise ValueError("Camp ID and Location are required")

        create_request(
            kind="add_camp",
            payload={
                "camp_id": camp_id,
                "location": location,
                "max_capacity": max_capacity,
                "available_food_packets": food,
                "available_medical_kits": medical,
                "volunteers": volunteers,
            },
        )
        flash("Camp request sent to Admin for approval.", "ok")
    except Exception as exc:  # beginner-friendly
        flash(f"Could not create camp request: {exc}", "err")
    return redirect(url_for("dashboard"))


@app.get("/victims/new")
def new_victim():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    return render_template("victim_form.html")


@app.post("/victims/register")
def register_victim():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    try:
        victim_id = request.form.get("victim_id", "").strip()
        name = request.form.get("name", "").strip()
        age = _to_int(request.form.get("age", "0"), min_value=0)
        address = request.form.get("address", "").strip()
        health = request.form.get("health_condition", "normal").strip().lower()
        injury = request.form.get("injury", "").strip()

        if not victim_id or not name:
            raise ValueError("Victim ID and Name are required")

        create_request(
            kind="register_victim",
            payload={
                "victim_id": victim_id,
                "name": name,
                "age": age,
                "address": address,
                "health_condition": health,
                "injury": injury,
            },
        )
        flash("Victim request sent to Admin for approval.", "ok")
    except Exception as exc:
        flash(f"Could not create victim request: {exc}", "err")

    return redirect(url_for("dashboard"))


@app.get("/resources/new")
def new_resources():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    return render_template("resources_form.html")


@app.post("/resources/update")
def update_resources():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    try:
        camp_id = request.form.get("camp_id", "").strip()
        food_add = _to_int(request.form.get("food_add", "0"), min_value=0)
        medical_add = _to_int(request.form.get("medical_add", "0"), min_value=0)

        if not camp_id:
            raise ValueError("Camp ID is required")

        create_request(
            kind="update_resources",
            payload={
                "camp_id": camp_id,
                "food_add": food_add,
                "medical_add": medical_add,
            },
        )
        flash("Resource update request sent to Admin for approval.", "ok")
    except Exception as exc:
        flash(f"Could not create resources request: {exc}", "err")

    return redirect(url_for("dashboard"))


@app.post("/distribute/food")
def distribute_food():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    try:
        create_request(kind="distribute_food", payload={})
        flash("Food distribution request sent to Admin for approval.", "ok")
    except Exception as exc:
        flash(f"Could not create distribution request: {exc}", "err")
    return redirect(url_for("dashboard"))


@app.post("/distribute/medical")
def distribute_medical():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    try:
        create_request(kind="distribute_medical", payload={})
        flash("Medical distribution request sent to Admin for approval.", "ok")
    except Exception as exc:
        flash(f"Could not create distribution request: {exc}", "err")
    return redirect(url_for("dashboard"))


@app.post("/help/request")
def help_request():
    """Create a help request ticket for admin to review.

    This does NOT place real phone calls; it stores the request so multiple
    people can submit help requests concurrently.
    """

    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))

    try:
        team = request.form.get("team", "").strip().lower()
        caller = request.form.get("caller", "").strip()
        message = request.form.get("message", "").strip()
        if not team:
            raise ValueError("Team is required")
        if not caller:
            raise ValueError("Caller number is required")
        if not message:
            raise ValueError("Message is required")

        create_request(
            kind="help_call",
            payload={
                "team": team,
                "caller": caller,
                "message": message,
            },
        )
        flash("Help request sent to Admin.", "ok")
    except Exception as exc:
        flash(f"Could not create help request: {exc}", "err")

    return redirect(url_for("dashboard"))


@app.get("/victims/search")
def victim_search_page():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    query = request.args.get("q", "").strip()
    results = system.search_victims(query) if query else []
    return render_template(
        "victim_search.html",
        query=query,
        results=results,
    )


# ----------------------------- Live Disaster Status (Public) -----------------------------

@app.get("/status")
def live_status():
    system = _system()
    active_disasters = system.get_active_disasters()
    camps = system.camps
    responders = system.responders
    alert = system.get_broadcast_alert()
    # Camp availability: those with space
    available_camps = [c for c in camps if getattr(c, "status", "active") == "active"]
    return render_template(
        "public_status.html",
        active_disasters=active_disasters,
        available_camps=available_camps,
        responders=responders,
        alert=alert,
    )


# ----------------------------- Missing Person Report/Search (Public) -----------------------------

@app.get("/missing/report")
def missing_report_page():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    return render_template("missing_person_form.html")


@app.post("/missing/report")
def missing_report_submit():
    system = _system()
    if not system.get_disaster_type():
        return redirect(url_for("setup"))
    try:
        name = request.form.get("name", "").strip()
        age_raw = request.form.get("age", "").strip()
        age = int(age_raw) if age_raw.isdigit() else None
        description = request.form.get("description", "").strip()
        last_seen = request.form.get("last_seen", "").strip()
        contact = request.form.get("contact", "").strip()

        if not name:
            raise ValueError("Name of missing person is required")
        if not contact:
            raise ValueError("Contact information is required")

        system.report_missing_person(
            name=name,
            age=age,
            description=description,
            last_seen=last_seen,
            reported_by=contact,
        )
        flash("Missing person report submitted. Admin has been notified.", "ok")
        return redirect(url_for("dashboard"))
    except Exception as exc:
        flash(f"Could not submit report: {exc}", "err")
        return redirect(url_for("missing_report_page"))


@app.get("/missing/search")
def missing_search_page():
    query = request.args.get("q", "").strip()
    results = []
    if query:
        system = _system()
        results = system.search_missing_persons(query=query)
    return render_template(
        "missing_person_search.html",
        query=query,
        results=results,
    )


def main() -> None:
    app.run(debug=True)


if __name__ == "__main__":
    main()
