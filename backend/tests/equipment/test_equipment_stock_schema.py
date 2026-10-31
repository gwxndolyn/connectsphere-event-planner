"""US5 equipment availability, PR 1 (SCRUM-124, story SCRUM-9): the catalogue's stock, out-of-service
count and storage location, the reservations table the check reads, and the seeded stock. The check
comes in SCRUM-125; see docs/testing/US5-equipment-availability.md."""

import uuid

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentReservation, EquipmentType
from app.seed import EQUIPMENT_STOCK, EQUIPMENT_TYPES, seed, seed_id
from app.user.models import UserRole
from tests.conftest import BACKEND_DIR
from tests.factories import NOW, make_event, make_user

REVISION = "20261101_1200_us5_equipment"


def make_type(db: Session, **fields) -> EquipmentType:
    equipment_type = EquipmentType(name=f"Test type {uuid.uuid4().hex[:8]}", **fields)
    db.add(equipment_type)
    db.flush()
    return equipment_type


def make_reservation(db: Session, **overrides) -> EquipmentReservation:
    # A reservation fulfils one approved line (US27, SCRUM-130).
    coordinator = make_user(db, UserRole.COORDINATOR)
    line = EquipmentRequestLine(
        event_id=make_event(db).id,
        equipment_type_id=make_type(db, total_quantity=5).id,
        quantity=2,
        requested_by_user_id=coordinator.id,
        status=EquipmentLineStatus.APPROVED,
        reviewed_by_user_id=make_user(db, UserRole.TECH_SUPPORT).id,
        reviewed_at=NOW,
    )
    db.add(line)
    db.flush()
    fields = {
        "request_line_id": line.id,
        "event_id": line.event_id,
        "equipment_type_id": line.equipment_type_id,
        "quantity": 2,
        "reserved_by_user_id": make_user(db, UserRole.TECH_SUPPORT).id,
    }
    reservation = EquipmentReservation(**(fields | overrides))
    db.add(reservation)
    db.flush()
    return reservation


def test_tc_us5_01_schema_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)

    assert {"total_quantity", "out_of_service_quantity", "storage_location"} <= {
        column["name"] for column in inspector.get_columns("equipment_types")
    }
    # US27 (SCRUM-130) adds the reservation's line and who reserved it.
    assert {column["name"] for column in inspector.get_columns("equipment_reservations")} >= {
        "id",
        "event_id",
        "equipment_type_id",
        "quantity",
        "created_at",
    }
    rls = db.execute(text("select relrowsecurity from pg_class where oid = 'equipment_reservations'::regclass"))
    assert rls.scalar_one() is True
    # SCRUM-125 sums a type's reservations.
    indexes = {index["name"]: index for index in inspector.get_indexes("equipment_reservations")}
    assert indexes["ix_equipment_reservations_equipment_type_id"]["column_names"] == ["equipment_type_id"]


def test_tc_us5_01_a_type_without_stock_defaults_to_none_owned(db: Session) -> None:
    # US26's catalogue entries, and any added without stock, own nothing until stock is recorded.
    equipment_type = make_type(db)
    db.expire(equipment_type)

    stored = db.get(EquipmentType, equipment_type.id)
    assert (stored.total_quantity, stored.out_of_service_quantity, stored.storage_location) == (0, 0, None)


def test_tc_us5_01_migrations_have_one_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert REVISION in {revision.revision for revision in script.walk_revisions()}


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"total_quantity": -1}, "equipment_types_stock_in_range"),
        ({"total_quantity": 5, "out_of_service_quantity": -1}, "equipment_types_stock_in_range"),
        ({"total_quantity": 5, "out_of_service_quantity": 6}, "equipment_types_stock_in_range"),
        ({"storage_location": "  "}, "equipment_types_storage_location_not_blank"),
    ],
    ids=["negative stock", "negative out of service", "more out of service than owned", "blank location"],
)
def test_tc_us5_02_stock_and_location_must_be_valid(db: Session, fields: dict, constraint: str) -> None:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_type(db, **fields)

    assert raised.value.orig.diag.constraint_name == constraint


def test_tc_us5_02_all_owned_units_may_be_out_of_service(db: Session) -> None:
    equipment_type = make_type(db, total_quantity=3, out_of_service_quantity=3, storage_location="AV store")

    assert equipment_type.out_of_service_quantity == 3


@pytest.mark.parametrize("quantity", [0, -1])
def test_tc_us5_02_reservation_quantity_must_be_positive(db: Session, quantity: int) -> None:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_reservation(db, quantity=quantity)

    assert raised.value.orig.diag.constraint_name == "equipment_reservations_quantity_positive"


@pytest.mark.parametrize("field", ["equipment_type_id", "event_id"])
def test_tc_us5_02_reservation_type_and_event_must_exist(db: Session, field: str) -> None:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_reservation(db, **{field: uuid.uuid4()})

    assert raised.value.orig.diag.constraint_name == f"equipment_reservations_{field}_fkey"


def _stock(db: Session) -> dict[str, tuple[int, int, str | None]]:
    seeded_ids = [seed_id("equipment-type", name) for name in EQUIPMENT_TYPES]
    types = db.scalars(select(EquipmentType).where(EquipmentType.id.in_(seeded_ids)))
    return {t.name: (t.total_quantity, t.out_of_service_quantity, t.storage_location) for t in types}


def test_tc_us5_03_seed_stocks_the_catalogue(db: Session) -> None:
    seed(db, now=NOW)
    stock = _stock(db)

    assert sorted(stock) == sorted(EQUIPMENT_TYPES) == sorted(EQUIPMENT_STOCK)
    for name, (total, out_of_service, location) in stock.items():
        assert total > 0, name
        assert location and location.strip(), name
    # Some units are damaged or under repair, so the check has something to exclude (AC 3).
    assert any(out_of_service > 0 for _, out_of_service, _ in stock.values())

    # Idempotent: a second run leaves the same stock.
    seed(db, now=NOW)
    assert _stock(db) == stock
