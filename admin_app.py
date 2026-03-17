"""Admin portal for Smart Disaster Relief Resource Management System.

This is intentionally a SEPARATE Flask app from the main web dashboard.

Run:
    python admin_app.py
Then open:
    http://127.0.0.1:5001

Admin features:
- Manage team permissions
- View responders + update status
- Allocate/unallocate responders

Data is shared via the same JSON files used by the dashboard app.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from functools import wraps
from flask import Flask, redirect, render_template, request, url_for, flash, session, Response

from relief_system import DisasterReliefSystem
from request_queue import (
    apply_request,
    approve_request,
    create_request,
    list_requests,
    mark_request_error,
    reject_request,
)


app = Flask(__name__)
app.secret_key = "aiac-relief-system-admin"  # simple secret for local demo


@app.template_filter('format_datetime')
def format_datetime_filter(value):
    """Format ISO datetime string to readable format."""
    if not value:
        return "N/A"
    try:
        if isinstance(value, str):
            # Handle ISO format with microseconds
            if '.' in value:
                dt = datetime.fromisoformat(value)
            else:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            dt = value
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except Exception:
        return str(value)[:19].replace('T', ' ')


# Default admin credentials (can be changed via settings)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def login_required(f):
    """Decorator to require login for admin routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please login to access the admin portal.", "err")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def _system() -> DisasterReliefSystem:
    # Create a fresh instance per request so it always reads latest JSON.
    return DisasterReliefSystem()


@app.context_processor
def inject_pending_count():
    """Inject pending requests count into all templates for notification badge."""
    try:
        pending = list_requests(status="pending")
        return {"pending_requests_count": len(pending)}
    except Exception:
        return {"pending_requests_count": 0}


@app.get("/")
def root():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_portal"))
    return redirect(url_for("login"))


@app.get("/login")
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_portal"))
    return render_template("admin_login.html")


@app.post("/login")
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["admin_logged_in"] = True
        session["admin_username"] = username
        flash("Login successful. Welcome to Admin Portal!", "ok")
        return redirect(url_for("admin_portal"))
    else:
        flash("Invalid username or password.", "err")
        return redirect(url_for("login"))


@app.get("/logout")
def logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_username", None)
    flash("You have been logged out.", "ok")
    return redirect(url_for("login"))


@app.get("/requests")
@login_required
def requests_inbox():
    system = _system()
    pending = list_requests(status="pending")
    decided = list_requests(status=None)
    decided = [r for r in decided if str(r.get("status")) in {"approved", "rejected"}]
    decided = decided[:50]

    # Get free responders grouped by role for disaster allocation
    responders_by_role = {}
    for role in ["ambulance", "police", "doctor", "fire_force", "diver"]:
        responders_by_role[role] = [
            {"id": r.responder_id, "name": r.name, "status": r.status}
            for r in system.responders_by_role(role)
        ]

    return render_template(
        "admin_requests.html",
        pending=pending,
        decided=decided,
        emergency_contacts=system.get_emergency_contacts(),
        responders_by_role=responders_by_role,
    )


@app.post("/requests/<request_id>/approve")
@login_required
def request_approve(request_id: str):
    system = _system()
    note = request.form.get("note", "").strip()

    item = None
    for r in list_requests(status=None):
        if str(r.get("id")) == str(request_id):
            item = r
            break
    if not item:
        flash("Request not found.", "err")
        return redirect(url_for("requests_inbox"))

    try:
        # For disaster reports, get selected responders from form
        selected_responders = request.form.getlist("responders")
        summary = apply_request(system, item, selected_responders=selected_responders)
        approve_request(request_id=str(request_id), note=note)
        flash(f"Approved: {summary}", "ok")
    except Exception as exc:
        mark_request_error(request_id=str(request_id), error=str(exc))
        flash(f"Could not approve request: {exc}", "err")
    return redirect(url_for("requests_inbox"))


@app.post("/requests/<request_id>/reject")
@login_required
def request_reject(request_id: str):
    note = request.form.get("note", "").strip()
    try:
        reject_request(request_id=str(request_id), note=note)
        flash("Request rejected.", "ok")
    except Exception as exc:
        flash(f"Could not reject request: {exc}", "err")
    return redirect(url_for("requests_inbox"))


@app.get("/admin")
@login_required
def admin_portal():
    system = _system()
    return render_template(
        "admin.html",
        report=system.report(),
        camps=system.camps,
        victims=system.victims,
        role_permissions=system.get_role_permissions(),
        emergency_contacts=system.get_emergency_contacts(),
        doctor_counts=system.status_counts(role="doctor"),
        responder_counts={
            "ambulance": system.status_counts(role="ambulance"),
            "fire_force": system.status_counts(role="fire_force"),
            "police": system.status_counts(role="police"),
            "diver": system.status_counts(role="diver"),
        },
        disaster_type=system.get_disaster_type(),
        disaster_subtype=system.get_disaster_subtype(),
        disaster_subtype_label=system.disaster_subtype_label(),
        activated_roles=system.activated_roles_for_disaster(),
        low_resource_alerts=system.get_low_resource_alerts(food_threshold=10, medical_threshold=5),
    )


@app.post("/admin")
@login_required
def admin_save():
    system = _system()
    try:
        perms = {
            "doctor": bool(request.form.get("perm_doctor")),
            "fire_force": bool(request.form.get("perm_fire_force")),
            "police": bool(request.form.get("perm_police")),
            "diver": bool(request.form.get("perm_diver")),
            "ambulance": bool(request.form.get("perm_ambulance")),
        }
        system.set_role_permissions(perms)
        flash("Admin permissions updated.", "ok")
    except Exception as exc:
        flash(f"Could not update permissions: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.get("/contacts")
@login_required
def contacts_page():
    system = _system()
    return render_template(
        "admin_contacts.html",
        emergency_contacts=system.get_emergency_contacts(),
    )


@app.post("/contacts")
@login_required
def contacts_save():
    system = _system()
    try:
        system.set_emergency_contacts(
            {
                "toll_free": request.form.get("toll_free", ""),
                "ambulance": request.form.get("ambulance", ""),
                "police": request.form.get("police", ""),
                "fire_force": request.form.get("fire_force", ""),
                "doctor": request.form.get("doctor", ""),
                "diver": request.form.get("diver", ""),
            }
        )
        flash("Emergency contacts updated.", "ok")
    except Exception as exc:
        flash(f"Could not update contacts: {exc}", "err")
    return redirect(url_for("contacts_page"))


@app.get("/admin/allocate")
@login_required
def admin_allocate_page():
    system = _system()
    return render_template(
        "admin_allocate.html",
        role_permissions=system.get_role_permissions(),
        responders=system.responders,
        victims=system.victims,
        camps=system.camps,
    )


@app.post("/admin/allocate")
@login_required
def admin_allocate_save():
    system = _system()

    try:
        responder_id = request.form.get("responder_id", "").strip()
        action = request.form.get("action", "allocate").strip().lower()

        if not responder_id:
            raise ValueError("Responder is required")

        if action == "unallocate":
            system.unallocate_responder(responder_id=responder_id)
            flash("Responder unallocated (set to free).", "ok")
        else:
            target_type = request.form.get("target_type", "").strip().lower()
            target_id = request.form.get("target_id", "").strip()
            note = request.form.get("note", "").strip()
            status = request.form.get("status", "busy").strip().lower()

            system.allocate_responder(
                responder_id=responder_id,
                target_type=target_type,
                target_id=target_id,
                note=note,
                status=status,
            )
            flash("Responder allocated successfully.", "ok")
    except PermissionError as exc:
        flash(str(exc), "err")
    except Exception as exc:
        flash(f"Allocation failed: {exc}", "err")

    return redirect(url_for("admin_allocate_page"))


@app.get("/responders")
@login_required
def responders_page():
    system = _system()

    role = request.args.get("role", "").strip().lower() or None
    responders = system.responders_by_role(role)

    return render_template(
        "responders.html",
        responders=responders,
        role=role,
        activated_roles=system.activated_roles_for_disaster(),
        role_permissions=system.get_role_permissions(),
        counts_all={
            "doctor": system.status_counts(role="doctor"),
            "fire_force": system.status_counts(role="fire_force"),
            "police": system.status_counts(role="police"),
            "diver": system.status_counts(role="diver"),
            "ambulance": system.status_counts(role="ambulance"),
        },
    )


@app.post("/responders/status")
@login_required
def responders_update_status():
    system = _system()
    role = request.form.get("role", "").strip().lower() or None

    try:
        responder_id = request.form.get("responder_id", "").strip()
        status = request.form.get("status", "").strip().lower()
        system.update_responder_status(responder_id=responder_id, status=status)
        flash("Responder status updated.", "ok")
    except PermissionError as exc:
        flash(str(exc), "err")
    except Exception as exc:
        flash(f"Could not update responder status: {exc}", "err")

    if role:
        return redirect(url_for("responders_page", role=role))
    return redirect(url_for("responders_page"))


@app.post("/responders/<responder_id>/complete")
@login_required
def complete_responder_task(responder_id):
    """Mark a responder's task as complete and set them to free."""
    system = _system()
    try:
        task_details = system.complete_responder_task(responder_id=responder_id)
        flash(f"Task completed for {task_details['responder_name']}. Status set to free.", "ok")
    except Exception as exc:
        flash(f"Could not complete task: {exc}", "err")
    return redirect(url_for("responders_page"))


@app.get("/responders/busy")
@login_required
def busy_responders_page():
    """View all busy responders with their current tasks."""
    system = _system()
    busy_responders = system.get_busy_responders()
    return render_template(
        "admin_busy_responders.html",
        busy_responders=busy_responders,
    )


@app.post("/responders/auto-complete")
@login_required
def auto_complete_tasks():
    """Auto-complete all overdue tasks."""
    system = _system()
    try:
        completed = system.auto_complete_overdue_tasks()
        if completed:
            names = [t['responder_name'] for t in completed]
            flash(f"Auto-completed {len(completed)} task(s): {', '.join(names)}", "ok")
        else:
            flash("No overdue tasks to complete.", "ok")
    except Exception as exc:
        flash(f"Error during auto-completion: {exc}", "err")
    return redirect(url_for("busy_responders_page"))


# ----------------------------- Direct Admin Actions (No Approval Needed) -----------------------------

@app.get("/camps/add")
@login_required
def add_camp_page():
    return render_template("admin_camp_form.html")


@app.post("/camps/add")
@login_required
def add_camp_submit():
    system = _system()
    try:
        camp_id = request.form.get("camp_id", "").strip()
        location = request.form.get("location", "").strip()
        max_capacity = int(request.form.get("max_capacity", "0"))
        food = int(request.form.get("available_food_packets", "0"))
        medical = int(request.form.get("available_medical_kits", "0"))
        volunteers_raw = request.form.get("volunteers", "").strip()
        volunteers = [v.strip() for v in volunteers_raw.split(",") if v.strip()]
        deadline = request.form.get("deadline", "").strip() or None

        if not camp_id or not location:
            raise ValueError("Camp ID and Location are required")

        system.add_camp(
            camp_id=camp_id,
            location=location,
            max_capacity=max_capacity,
            available_food_packets=food,
            available_medical_kits=medical,
            volunteers=volunteers,
            deadline=deadline,
        )
        flash("Camp added successfully.", "ok")
    except Exception as exc:
        flash(f"Could not add camp: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.post("/camps/<camp_id>/close")
@login_required
def close_camp(camp_id):
    system = _system()
    try:
        system.close_camp(camp_id=camp_id)
        flash(f"Camp {camp_id} closed.", "ok")
    except Exception as exc:
        flash(f"Could not close camp: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.post("/camps/<camp_id>/reopen")
@login_required
def reopen_camp(camp_id):
    system = _system()
    try:
        system.reopen_camp(camp_id=camp_id)
        flash(f"Camp {camp_id} reopened.", "ok")
    except Exception as exc:
        flash(f"Could not reopen camp: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.post("/camps/<camp_id>/delete")
@login_required
def delete_camp(camp_id):
    system = _system()
    try:
        # Force delete for admin
        system.delete_camp(camp_id=camp_id, force=True)
        flash(f"Camp {camp_id} deleted.", "ok")
    except Exception as exc:
        flash(f"Could not delete camp: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.get("/victims/register")
@login_required
def register_victim_page():
    return render_template("admin_victim_form.html")


@app.post("/victims/register")
@login_required
def register_victim_submit():
    system = _system()
    try:
        victim_id = request.form.get("victim_id", "").strip()
        name = request.form.get("name", "").strip()
        age = int(request.form.get("age", "0"))
        address = request.form.get("address", "").strip()
        health = request.form.get("health_condition", "normal").strip().lower()
        injury = request.form.get("injury", "").strip()

        if not victim_id or not name:
            raise ValueError("Victim ID and Name are required")

        victim = system.register_victim(
            victim_id=victim_id,
            name=name,
            age=age,
            address=address,
            health_condition=health,
            injury=injury,
        )
        if victim.doctor_name:
            flash(
                f"Victim registered and assigned to Camp {victim.assigned_camp}. "
                f"Doctor auto-allocated: {victim.doctor_name} ({victim.doctor_specialty}) for injury: {injury}",
                "ok",
            )
        else:
            flash(f"Victim registered and assigned to Camp {victim.assigned_camp}.", "ok")
    except Exception as exc:
        flash(f"Could not register victim: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.post("/victims/delete/<victim_id>")
@login_required
def delete_victim(victim_id):
    system = _system()
    try:
        system.delete_victim(victim_id=victim_id)
        flash(f"Victim {victim_id} deleted successfully.", "ok")
    except ValueError as exc:
        flash(f"Cannot delete victim: {exc}", "err")
    except Exception as exc:
        flash(f"Error deleting victim: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.get("/resources/update")
@login_required
def update_resources_page():
    system = _system()
    return render_template("admin_resources_form.html", camps=system.camps)


@app.post("/resources/update")
@login_required
def update_resources_submit():
    system = _system()
    try:
        camp_id = request.form.get("camp_id", "").strip()
        food_add = int(request.form.get("food_add", "0"))
        medical_add = int(request.form.get("medical_add", "0"))

        if not camp_id:
            raise ValueError("Camp ID is required")

        system.update_camp_resources(camp_id=camp_id, food_add=food_add, medical_add=medical_add)
        flash("Resources updated successfully.", "ok")
    except Exception as exc:
        flash(f"Could not update resources: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.post("/distribute/food")
@login_required
def distribute_food():
    system = _system()
    try:
        count = system.distribute_food()
        # Log the distribution
        for camp in system.camps:
            if camp.current_occupancy > 0:
                system.log_distribution("FOOD", camp.camp_id, count, "Food packets distributed")
        flash(f"Food distribution complete. Packets distributed: {count}", "ok")
    except Exception as exc:
        flash(f"Food distribution failed: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.post("/distribute/medical")
@login_required
def distribute_medical():
    system = _system()
    try:
        count = system.distribute_medical()
        # Log the distribution
        for camp in system.camps:
            if camp.current_occupancy > 0:
                system.log_distribution("MEDICAL", camp.camp_id, count, "Medical kits distributed")
        flash(f"Medical kit distribution complete. Kits distributed: {count}", "ok")
    except Exception as exc:
        flash(f"Medical distribution failed: {exc}", "err")
    return redirect(url_for("admin_portal"))


# ----------------------------- Volunteer Management -----------------------------

@app.get("/volunteers")
@login_required
def volunteers_page():
    system = _system()
    volunteers = system.get_all_volunteers()
    camps = system.camps
    return render_template(
        "admin_volunteers.html",
        volunteers=volunteers,
        camps=camps,
    )


@app.get("/volunteers/add")
@login_required
def add_volunteer_page():
    system = _system()
    return render_template("admin_volunteer_form.html", camps=system.camps)


@app.post("/volunteers/add")
@login_required
def add_volunteer_submit():
    system = _system()
    try:
        volunteer_id = request.form.get("volunteer_id", "").strip()
        name = request.form.get("name", "").strip()
        assigned_camp = request.form.get("assigned_camp", "").strip() or None
        task = request.form.get("task", "").strip() or None

        if not volunteer_id or not name:
            raise ValueError("Volunteer ID and Name are required")

        system.add_volunteer(
            volunteer_id=volunteer_id,
            name=name,
            assigned_camp=assigned_camp,
            task=task,
        )
        flash(f"Volunteer {name} added successfully.", "ok")
    except Exception as exc:
        flash(f"Could not add volunteer: {exc}", "err")
    return redirect(url_for("volunteers_page"))


@app.post("/volunteers/<volunteer_id>/assign")
@login_required
def assign_volunteer(volunteer_id):
    system = _system()
    try:
        camp_id = request.form.get("camp_id", "").strip()
        task = request.form.get("task", "").strip() or None

        if not camp_id:
            raise ValueError("Camp ID is required for assignment")

        system.assign_volunteer_to_camp(
            volunteer_id=volunteer_id,
            camp_id=camp_id,
            task=task,
        )
        flash(f"Volunteer assigned to Camp {camp_id}.", "ok")
    except Exception as exc:
        flash(f"Could not assign volunteer: {exc}", "err")
    return redirect(url_for("volunteers_page"))


@app.post("/volunteers/<volunteer_id>/delete")
@login_required
def delete_volunteer(volunteer_id):
    system = _system()
    try:
        system.delete_volunteer(volunteer_id=volunteer_id)
        flash(f"Volunteer {volunteer_id} deleted.", "ok")
    except Exception as exc:
        flash(f"Could not delete volunteer: {exc}", "err")
    return redirect(url_for("volunteers_page"))


# ----------------------------- Victim Health & Transfer -----------------------------

@app.get("/victims/<victim_id>/update")
@login_required
def update_victim_page(victim_id):
    system = _system()
    victim = system.victim_by_id(victim_id)
    if not victim:
        flash("Victim not found.", "err")
        return redirect(url_for("admin_portal"))
    camps = system.camps
    return render_template(
        "admin_victim_update.html",
        victim=victim,
        camps=camps,
    )


@app.post("/victims/<victim_id>/health")
@login_required
def update_victim_health(victim_id):
    system = _system()
    try:
        health_condition = request.form.get("health_condition", "").strip()
        
        if not health_condition:
            raise ValueError("Health condition is required")

        victim = system.update_victim_health(
            victim_id=victim_id,
            health_condition=health_condition,
        )
        flash(f"Victim {victim_id} health updated to '{health_condition}'.", "ok")
    except Exception as exc:
        flash(f"Could not update victim health: {exc}", "err")
    return redirect(url_for("admin_portal"))


@app.post("/victims/<victim_id>/transfer")
@login_required
def transfer_victim(victim_id):
    system = _system()
    try:
        target_camp_id = request.form.get("target_camp_id", "").strip()
        
        if not target_camp_id:
            raise ValueError("Target camp is required")

        victim = system.transfer_victim(
            victim_id=victim_id,
            target_camp_id=target_camp_id,
        )
        flash(f"Victim {victim_id} transferred to Camp {target_camp_id}.", "ok")
    except Exception as exc:
        flash(f"Could not transfer victim: {exc}", "err")
    return redirect(url_for("admin_portal"))


# ----------------------------- Occupancy Alerts -----------------------------

@app.get("/occupancy")
@login_required
def occupancy_page():
    system = _system()
    camps_occupancy = system.get_all_camps_occupancy()
    high_occupancy_alerts = system.get_high_occupancy_alerts(threshold=90.0)
    return render_template(
        "admin_occupancy.html",
        camps_occupancy=camps_occupancy,
        high_occupancy_alerts=high_occupancy_alerts,
    )


# ----------------------------- Disaster Tracking -----------------------------

@app.get("/disasters")
@login_required
def disasters_page():
    """View all active and past disasters."""
    system = _system()
    active_disasters = system.get_active_disasters()
    all_disasters = system.get_all_disasters()
    resolved_disasters = [d for d in all_disasters if d.status in {"resolved", "closed"}]
    return render_template(
        "admin_disasters.html",
        active_disasters=active_disasters,
        resolved_disasters=resolved_disasters,
    )


@app.get("/disasters/<disaster_id>")
@login_required
def disaster_detail_page(disaster_id):
    """View detailed status of a specific disaster."""
    system = _system()
    try:
        summary = system.get_disaster_summary(disaster_id)
        disaster = system.disaster_by_id(disaster_id)
        # Get available responders for assignment
        available_responders = [r for r in system.responders if r.status == "free"]
        available_camps = [c for c in system.camps if c.status == "active"]
        return render_template(
            "admin_disaster_detail.html",
            disaster=disaster,
            summary=summary,
            available_responders=available_responders,
            available_camps=available_camps,
        )
    except Exception as exc:
        flash(f"Error loading disaster: {exc}", "err")
        return redirect(url_for("disasters_page"))


@app.post("/disasters/<disaster_id>/status")
@login_required
def update_disaster_status(disaster_id):
    """Update the status of a disaster."""
    system = _system()
    try:
        status = request.form.get("status", "").strip()
        message = request.form.get("message", "").strip()
        
        if not status:
            raise ValueError("Status is required")
        
        system.update_disaster_status(
            disaster_id=disaster_id,
            status=status,
            update_message=message or None,
            updated_by="Admin",
        )
        flash(f"Disaster status updated to '{status}'.", "ok")
    except Exception as exc:
        flash(f"Could not update disaster status: {exc}", "err")
    return redirect(url_for("disaster_detail_page", disaster_id=disaster_id))


@app.post("/disasters/<disaster_id>/update")
@login_required
def add_disaster_update(disaster_id):
    """Add a status update/note to a disaster."""
    system = _system()
    try:
        message = request.form.get("message", "").strip()
        
        if not message:
            raise ValueError("Update message is required")
        
        system.add_disaster_update(
            disaster_id=disaster_id,
            message=message,
            updated_by="Admin",
        )
        flash("Update added to disaster log.", "ok")
    except Exception as exc:
        flash(f"Could not add update: {exc}", "err")
    return redirect(url_for("disaster_detail_page", disaster_id=disaster_id))


@app.post("/disasters/<disaster_id>/assign-responder")
@login_required
def assign_responder_to_disaster(disaster_id):
    """Assign a responder to a disaster."""
    system = _system()
    try:
        responder_id = request.form.get("responder_id", "").strip()
        task = request.form.get("task", "").strip()
        
        if not responder_id:
            raise ValueError("Responder is required")
        
        system.assign_responder_to_disaster(
            disaster_id=disaster_id,
            responder_id=responder_id,
            task_description=task or None,
        )
        flash("Responder assigned to disaster.", "ok")
    except Exception as exc:
        flash(f"Could not assign responder: {exc}", "err")
    return redirect(url_for("disaster_detail_page", disaster_id=disaster_id))


@app.post("/disasters/<disaster_id>/unassign-responder/<responder_id>")
@login_required
def unassign_responder_from_disaster(disaster_id, responder_id):
    """Remove a responder from a disaster."""
    system = _system()
    try:
        system.unassign_responder_from_disaster(
            disaster_id=disaster_id,
            responder_id=responder_id,
        )
        flash("Responder unassigned and freed.", "ok")
    except Exception as exc:
        flash(f"Could not unassign responder: {exc}", "err")
    return redirect(url_for("disaster_detail_page", disaster_id=disaster_id))


@app.post("/disasters/<disaster_id>/assign-camp")
@login_required
def assign_camp_to_disaster(disaster_id):
    """Assign a relief camp to a disaster."""
    system = _system()
    try:
        camp_id = request.form.get("camp_id", "").strip()
        
        if not camp_id:
            raise ValueError("Camp is required")
        
        system.assign_camp_to_disaster(
            disaster_id=disaster_id,
            camp_id=camp_id,
        )
        flash("Camp assigned to disaster.", "ok")
    except Exception as exc:
        flash(f"Could not assign camp: {exc}", "err")
    return redirect(url_for("disaster_detail_page", disaster_id=disaster_id))


# Backward-compatible endpoint aliases for older templates.
app.add_url_rule(
    "/disasters/<disaster_id>/status",
    endpoint="update_disaster_status_route",
    view_func=update_disaster_status,
    methods=["POST"],
)
app.add_url_rule(
    "/disasters/<disaster_id>/update",
    endpoint="add_disaster_update_route",
    view_func=add_disaster_update,
    methods=["POST"],
)
app.add_url_rule(
    "/disasters/<disaster_id>/assign-responder",
    endpoint="assign_disaster_responder_route",
    view_func=assign_responder_to_disaster,
    methods=["POST"],
)
app.add_url_rule(
    "/disasters/<disaster_id>/unassign-responder/<responder_id>",
    endpoint="unassign_disaster_responder_route",
    view_func=unassign_responder_from_disaster,
    methods=["POST"],
)
app.add_url_rule(
    "/disasters/<disaster_id>/assign-camp",
    endpoint="assign_disaster_camp_route",
    view_func=assign_camp_to_disaster,
    methods=["POST"],
)


# ----------------------------- Broadcast Alert -----------------------------

@app.get("/broadcast")
@login_required
def broadcast_page():
    system = _system()
    alert = system.get_broadcast_alert()
    return render_template("admin_broadcast.html", alert=alert)


@app.post("/broadcast")
@login_required
def broadcast_save():
    system = _system()
    try:
        message = request.form.get("message", "").strip()
        if not message:
            raise ValueError("Alert message cannot be empty")
        system.set_broadcast_alert(message=message, set_by="Admin")
        flash("Broadcast alert set. All users will see this message.", "ok")
    except Exception as exc:
        flash(f"Could not set alert: {exc}", "err")
    return redirect(url_for("broadcast_page"))


@app.post("/broadcast/clear")
@login_required
def broadcast_clear():
    system = _system()
    try:
        system.clear_broadcast_alert()
        flash("Broadcast alert cleared.", "ok")
    except Exception as exc:
        flash(f"Could not clear alert: {exc}", "err")
    return redirect(url_for("broadcast_page"))


# ----------------------------- CSV Export -----------------------------

@app.get("/export/camps.csv")
@login_required
def export_camps_csv():
    system = _system()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Camp ID", "Location", "Max Capacity", "Current Occupancy", "Food Packets", "Medical Kits", "Status", "Deadline"])
    for camp in system.camps:
        writer.writerow([
            camp.camp_id,
            camp.location,
            camp.max_capacity,
            camp.current_occupancy,
            camp.available_food_packets,
            camp.available_medical_kits,
            getattr(camp, "status", "active"),
            getattr(camp, "deadline", ""),
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=camps.csv"},
    )


@app.get("/export/victims.csv")
@login_required
def export_victims_csv():
    system = _system()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Victim ID", "Name", "Age", "Address", "Health Condition", "Injury", "Assigned Camp", "Doctor"])
    for v in system.victims:
        writer.writerow([
            v.victim_id,
            v.name,
            v.age,
            v.address,
            v.health_condition,
            getattr(v, "injury", ""),
            v.assigned_camp,
            getattr(v, "doctor_name", ""),
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=victims.csv"},
    )


@app.get("/export/responders.csv")
@login_required
def export_responders_csv():
    system = _system()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Responder ID", "Name", "Role", "Status", "Current Task"])
    for r in system.responders:
        writer.writerow([
            r.responder_id,
            r.name,
            r.role,
            r.status,
            getattr(r, "current_task", ""),
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=responders.csv"},
    )


# ----------------------------- Analytics -----------------------------

@app.get("/analytics")
@login_required
def analytics_page():
    system = _system()
    camps = system.camps
    victims = system.victims
    responders = system.responders

    # Camp occupancy data for chart
    camp_labels = [c.camp_id for c in camps]
    camp_occupancy = [c.current_occupancy for c in camps]
    camp_capacity = [c.max_capacity for c in camps]

    # Victim health distribution
    health_counts = {}
    for v in victims:
        h = v.health_condition or "unknown"
        health_counts[h] = health_counts.get(h, 0) + 1

    # Responder status distribution
    responder_status = {}
    for r in responders:
        s = r.status or "unknown"
        responder_status[s] = responder_status.get(s, 0) + 1

    # Role distribution
    role_counts = {}
    for r in responders:
        role_counts[r.role] = role_counts.get(r.role, 0) + 1

    return render_template(
        "admin_analytics.html",
        camp_labels=camp_labels,
        camp_occupancy=camp_occupancy,
        camp_capacity=camp_capacity,
        health_counts=health_counts,
        responder_status=responder_status,
        role_counts=role_counts,
        total_victims=len(victims),
        total_camps=len(camps),
        total_responders=len(responders),
    )


# ----------------------------- Missing Persons -----------------------------

@app.get("/missing-persons")
@login_required
def missing_persons_page():
    system = _system()
    all_missing = system.get_all_missing_persons()
    return render_template("admin_missing_persons.html", missing_persons=all_missing)


@app.post("/missing-persons/<record_id>/found")
@login_required
def mark_person_found(record_id):
    system = _system()
    try:
        note = request.form.get("note", "").strip() or None
        system.mark_person_found(record_id=record_id, found_note=note)
        flash("Person marked as found.", "ok")
    except Exception as exc:
        flash(f"Could not update record: {exc}", "err")
    return redirect(url_for("missing_persons_page"))


@app.post("/missing-persons/<record_id>/delete")
@login_required
def delete_missing_record(record_id):
    system = _system()
    try:
        records = system.get_all_missing_persons()
        updated = [r for r in records if r.get("id") != record_id]
        system._save_missing(updated)
        flash("Missing person record deleted.", "ok")
    except Exception as exc:
        flash(f"Could not delete record: {exc}", "err")
    return redirect(url_for("missing_persons_page"))


# ----------------------------- Resource Needs Tracker -----------------------------

@app.post("/disasters/<disaster_id>/resource-needs")
@login_required
def add_resource_need(disaster_id):
    system = _system()
    try:
        item = request.form.get("item", "").strip()
        quantity = int(request.form.get("quantity", "1"))
        priority = request.form.get("priority", "normal").strip()
        note = request.form.get("note", "").strip() or None
        if not item:
            raise ValueError("Resource item name is required")
        system.add_resource_need(
            disaster_id=disaster_id,
            item=item,
            quantity=quantity,
            priority=priority,
            note=note,
        )
        flash(f"Resource need '{item}' added.", "ok")
    except Exception as exc:
        flash(f"Could not add resource need: {exc}", "err")
    return redirect(url_for("disaster_detail_page", disaster_id=disaster_id))


@app.post("/disasters/<disaster_id>/resource-needs/<need_id>/fulfill")
@login_required
def fulfill_resource_need(disaster_id, need_id):
    system = _system()
    try:
        system.fulfill_resource_need(disaster_id=disaster_id, need_id=need_id)
        flash("Resource need marked as fulfilled.", "ok")
    except Exception as exc:
        flash(f"Could not update resource need: {exc}", "err")
    return redirect(url_for("disaster_detail_page", disaster_id=disaster_id))


# ----------------------------- Disaster Print/PDF -----------------------------

@app.get("/disasters/<disaster_id>/print")
@login_required
def disaster_print_page(disaster_id):
    system = _system()
    try:
        summary = system.get_disaster_summary(disaster_id)
        disaster = system.disaster_by_id(disaster_id)
        now = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        return render_template(
            "disaster_print.html",
            disaster=disaster,
            summary=summary,
            print_time=now,
        )
    except Exception as exc:
        flash(f"Error loading disaster for print: {exc}", "err")
        return redirect(url_for("disasters_page"))


def main() -> None:
    # Running on a different port keeps admin UI separate from dashboard.
    app.run(debug=True, port=5001)


if __name__ == "__main__":
    main()
