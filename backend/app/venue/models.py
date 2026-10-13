import uuid
from datetime import time

from sqlalchemy import ARRAY, CheckConstraint, Integer, Text, Time, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# DECISION-PENDING: D18 — SCRUM-87 only gives examples (projector, stage, wifi; wheelchair, lift;
# theatre, classroom, banquet). These are the assumed vocabularies, so US2's filters and the
# venue form agree on spelling. The migration's CHECKs hold the same lists; change both together.
FACILITIES = (
    "projector",
    "screen",
    "sound_system",
    "microphone",
    "stage",
    "wifi",
    "whiteboard",
    "video_conferencing",
    "power_outlets",
)
ACCESSIBILITY_FEATURES = (
    "wheelchair",
    "lift",
    "accessible_toilet",
    "hearing_loop",
    "step_free_entrance",
)
ROOM_LAYOUTS = (
    "theatre",
    "classroom",
    "banquet",
    "boardroom",
    "u_shape",
    "cabaret",
    "standing",
)


class Venue(Base):
    """A bookable venue in the catalogue (US20, SCRUM-87). One venue hosts one event at a time;
    there are no separately bookable rooms inside it. Setup and turnaround buffers belong to the
    venue only: a booking can't override them for a single event (AC 7). The table's CHECK
    constraints are the source of truth; the class mirrors them for readers."""

    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="venues_name_not_blank"),
        CheckConstraint("btrim(location) <> ''", name="venues_location_not_blank"),
        CheckConstraint("capacity > 0", name="venues_capacity_positive"),
        CheckConstraint("closes_at > opens_at", name="venues_hours_valid"),
        CheckConstraint("setup_minutes >= 0", name="venues_setup_minutes_non_negative"),
        CheckConstraint("turnaround_minutes >= 0", name="venues_turnaround_minutes_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text)
    capacity: Mapped[int] = mapped_column(Integer)
    facilities: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    accessibility_features: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    room_layouts: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    opens_at: Mapped[time] = mapped_column(Time)
    closes_at: Mapped[time] = mapped_column(Time)
    setup_minutes: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    turnaround_minutes: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
