from datetime import time

import streamlit as st

from pawpal_system import Owner, Pet, Scheduler, Task
from ai_assistant import plan_from_request


def pet_name_for(task, owner):
    for pet in owner.pets:
        if task in pet.tasks:
            return pet.name
    return "?"

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

if "owner" not in st.session_state:
    st.session_state.owner = Owner("Jordan", available_minutes=90)
owner = st.session_state.owner

st.markdown(
    """
Welcome to PawPal+ — a pet care planning assistant.

Set up your day below: tell us who you are and how much time you have,
add your pets, give them care tasks, and generate today's schedule.
"""
)

with st.expander("How to use", expanded=False):
    st.markdown(
        """
1. **Owner** — enter your name, how many minutes you have today, and optionally
   when your day starts and ends.
2. **Pets** — add each of your pets (name, species, and optionally breed).
3. **Plan with AI** — describe what your pets need in plain English. The AI looks
   up pet-care facts, drafts tasks, checks them for safety, and adds the valid
   ones for you.
4. **Tasks** — or add tasks by hand, and mark them complete as you do them
   (daily/weekly tasks come back automatically). Use the filters to view one
   pet's tasks or check what's still pending.
5. **Today's Schedule** — click *Generate schedule* to build your day.
   You'll also be warned if two tasks are booked at the same time.
6. **Reset app** — clears everything (owner, pets, and tasks) so you can start over.
"""
    )

with st.expander("How scheduling works", expanded=False):
    st.markdown(
        """
- High-priority tasks are placed first, then medium, then low.
- Tasks only make the plan if they fit in your remaining time.
- The plan is shown in time order, like a daily agenda.
- Tasks that don't fit are listed as skipped, along with how many
  more minutes you would need to fit them in.
- Completed tasks are left out automatically.
"""
    )

if st.button("🔄 Reset app"):
    st.session_state.clear()
    st.rerun()

st.divider()

st.subheader("Owner")
owner.name = st.text_input("Owner name", value=owner.name)
owner.update_availability(
    int(st.number_input("Time available today (minutes)", min_value=10, max_value=600, value=owner.available_minutes))
)
dcol1, dcol2 = st.columns(2)
with dcol1:
    day_start = st.time_input("Day starts", value=time(7, 0))
with dcol2:
    day_end = st.time_input("Day ends", value=time(21, 0))
owner.set_preference("day_start", day_start.strftime("%H:%M"))
owner.set_preference("day_end", day_end.strftime("%H:%M"))

st.subheader("Pets")
col1, col2, col3 = st.columns(3)
with col1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col2:
    species = st.selectbox("Species", ["dog", "cat", "other"])
with col3:
    breed = st.text_input("Breed (optional)", value="")

if st.button("Add pet"):
    owner.add_pet(Pet(pet_name, species, breed))

if owner.pets:
    st.write("Current pets: " + ", ".join(pet.describe() for pet in owner.pets))
else:
    st.info("No pets yet. Add one above.")

st.subheader("🤖 Plan with AI")
if owner.pets:
    st.caption(
        "Describe what your pets need in plain English. The AI looks up pet-care "
        "facts, drafts tasks, checks them, and adds the valid ones below."
    )
    ai_request = st.text_area(
        "What do your pets need today?",
        placeholder="e.g. Walk my senior dog in the morning and feed my cat twice a day",
        key="ai_request",
    )
    if st.button("Plan with AI"):
        if not ai_request.strip():
            st.info("Type a request first.")
        else:
            try:
                with st.spinner("Thinking..."):
                    result = plan_from_request(owner, ai_request)
            except Exception as error:
                st.error(f"AI planning failed: {error}")
            else:
                if result.facts:
                    with st.expander("Pet-care facts the AI used (RAG)", expanded=False):
                        for fact in result.facts:
                            st.markdown(f"- {fact.text}")
                if result.accepted:
                    st.success(f"Added {len(result.accepted)} task(s) to your pets:")
                    st.table(
                        [
                            {
                                "Pet": name,
                                "Task": task.description,
                                "Due": task.due_time or "anytime",
                                "Minutes": task.duration,
                                "Priority": task.priority,
                                "Repeats": task.frequency,
                            }
                            for name, task in result.accepted
                        ]
                    )
                else:
                    st.info("The AI did not produce any tasks for this request.")
                for warning in result.warnings:
                    st.warning(f"Rejected by guardrails: {warning}")
                for conflict in result.conflicts:
                    st.warning(f"⚠ {conflict}")
else:
    st.caption("Add a pet first, then the AI can plan tasks for it.")

st.subheader("Tasks")
if owner.pets:
    col1, col2 = st.columns(2)
    with col1:
        task_pet = st.selectbox("Pet", [pet.name for pet in owner.pets])
    with col2:
        description = st.text_input("Task", value="Morning walk")
    col3, col4, col5, col6 = st.columns(4)
    with col3:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col4:
        due = st.time_input("Due time", value=time(8, 0))
    with col5:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
    with col6:
        frequency = st.selectbox("Repeats", ["once", "daily", "weekly"])

    if st.button("Add task"):
        pet = next(p for p in owner.pets if p.name == task_pet)
        pet.add_task(Task(description, int(duration), due.strftime("%H:%M"), priority, frequency))

    scheduler = Scheduler(owner)

    pending = [(p, t) for p in owner.pets for t in p.tasks if not t.completed]
    if pending:
        labels = [f"{t.description} ({p.name}, {t.due_time or 'anytime'})" for p, t in pending]
        ccol1, ccol2 = st.columns([3, 1])
        with ccol1:
            chosen = st.selectbox("Mark a task complete", labels)
        with ccol2:
            st.write("")
            if st.button("Complete"):
                p, t = pending[labels.index(chosen)]
                follow_up = p.complete_task(t)
                if follow_up:
                    st.success(
                        f"Done! Since it repeats {follow_up.frequency}, the next one was created for {follow_up.due_date} at {follow_up.due_time}."
                    )
                else:
                    st.success("Done!")

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        pet_filter = st.selectbox("Show tasks for", ["All pets"] + [p.name for p in owner.pets])
    with fcol2:
        status_filter = st.selectbox("Status", ["All", "Pending", "Done"])

    tasks = scheduler.get_all_tasks() if pet_filter == "All pets" else scheduler.filter_by_pet(pet_filter)
    if status_filter != "All":
        tasks = [t for t in tasks if t.completed == (status_filter == "Done")]

    rows = [
        {
            "Pet": pet_name_for(t, owner),
            "Task": t.description,
            "Date": t.due_date if t.due_date else "today",
            "Due": t.due_time if t.due_time else "anytime",
            "Minutes": t.duration,
            "Priority": t.priority,
            "Repeats": t.frequency,
            "Done": t.completed,
        }
        for t in scheduler.sort_by_time(tasks)
    ]
    if rows:
        st.table(rows)
    else:
        st.info("No tasks match. Add one above or change the filters.")
else:
    st.caption("Add a pet first, then you can give it tasks.")

st.divider()

st.subheader("Today's Schedule")

if st.button("Generate schedule"):
    scheduler = Scheduler(owner)
    for conflict in scheduler.find_conflicts():
        st.warning(f"⚠ {conflict}")
    plan = scheduler.generate_plan()
    if plan:
        st.table(
            [
                {
                    "When": t.due_time if t.due_time else "anytime",
                    "Task": t.description,
                    "Pet": pet_name_for(t, owner),
                    "Minutes": t.duration,
                    "Priority": t.priority,
                }
                for t in plan
            ]
        )
        used = sum(t.duration for t in plan)
        st.caption(
            f"Scheduled {len(plan)} of {len(owner.get_all_tasks())} tasks — {used} of {owner.available_minutes} minutes used."
        )
        minutes_left = owner.available_minutes - used
        for t in owner.get_all_tasks():
            if not t.completed and not t.due_date and t not in plan:
                st.warning(
                    f"Skipped: {t.description} ({pet_name_for(t, owner)}, {t.duration} min, {t.priority} priority) — needs {t.duration - minutes_left} more min."
                )
    else:
        st.info("Nothing to schedule yet — add some tasks first.")
