import datetime
import pytest
from sqlalchemy.orm import sessionmaker
from db.base import get_engine, Base


@pytest.fixture(scope="module")
def engine():
    e = get_engine("sqlite:///:memory:")
    import db.models
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


PARSED_SLEEP = {
    "sleep_date": "2026-06-21",
    "total_sleep_min": 450,
    "deep_sleep_min": 90,
    "light_sleep_min": 240,
    "rem_sleep_min": 90,
    "awake_min": 30,
    "sleep_score": 82,
    "resting_hr": 54,
    "sleep_start": "2026-06-21T23:00:00+00:00",
    "sleep_end": "2026-06-22T07:00:00+00:00",
}

PARSED_ACTIVITY = {
    "garmin_activity_id": 11111111,
    "activity_type": "running",
    "activity_date": "2026-06-21",
    "duration_min": 60,
    "calories_burned": 550,
    "avg_hr": 145,
    "max_hr": 175,
    "steps": 8200,
    "distance_km": 10.0,
    "hr_zone_1_min": 5,
    "hr_zone_2_min": 10,
    "hr_zone_3_min": 20,
    "hr_zone_4_min": 20,
    "hr_zone_5_min": 5,
}


def test_upsert_sleep_inserts_new_record(session):
    from garmin.db_sync import upsert_sleep
    from db.models import Sleep
    upsert_sleep(session, PARSED_SLEEP)
    session.flush()
    result = session.query(Sleep).filter_by(
        sleep_date=datetime.date(2026, 6, 21)
    ).one()
    assert result.total_sleep_min == 450
    assert result.sleep_score == 82
    assert result.resting_hr == 54


def test_upsert_sleep_updates_existing_record(session):
    from garmin.db_sync import upsert_sleep
    from db.models import Sleep
    # Insert first
    upsert_sleep(session, PARSED_SLEEP)
    session.flush()
    # Update with new score
    updated = dict(PARSED_SLEEP, sleep_score=90, sleep_date="2026-06-21")
    upsert_sleep(session, updated)
    session.flush()
    results = session.query(Sleep).filter_by(
        sleep_date=datetime.date(2026, 6, 21)
    ).all()
    assert len(results) == 1  # no duplicate
    assert results[0].sleep_score == 90


def test_upsert_sleep_converts_string_dates(session):
    from garmin.db_sync import upsert_sleep
    from db.models import Sleep
    data = dict(PARSED_SLEEP, sleep_date="2026-06-20")
    upsert_sleep(session, data)
    session.flush()
    result = session.query(Sleep).filter_by(
        sleep_date=datetime.date(2026, 6, 20)
    ).one()
    assert isinstance(result.sleep_start, datetime.datetime)


def test_upsert_sleep_handles_none_timestamps(session):
    from garmin.db_sync import upsert_sleep
    from db.models import Sleep
    data = dict(PARSED_SLEEP, sleep_date="2026-06-19",
                sleep_start=None, sleep_end=None)
    upsert_sleep(session, data)
    session.flush()
    result = session.query(Sleep).filter_by(
        sleep_date=datetime.date(2026, 6, 19)
    ).one()
    assert result.sleep_start is None


def test_insert_activities_inserts_new(session):
    from garmin.db_sync import insert_activities
    count = insert_activities(session, [PARSED_ACTIVITY])
    session.flush()
    assert count == 1


def test_insert_activities_skips_existing(session):
    from garmin.db_sync import insert_activities
    from db.models import Activity
    # First insert
    insert_activities(session, [PARSED_ACTIVITY])
    session.flush()
    # Second insert — same garmin_activity_id
    count = insert_activities(session, [PARSED_ACTIVITY])
    session.flush()
    assert count == 0
    total = session.query(Activity).filter_by(
        garmin_activity_id=PARSED_ACTIVITY["garmin_activity_id"]
    ).count()
    assert total == 1  # still just one


def test_insert_activities_converts_date_string(session):
    from garmin.db_sync import insert_activities
    from db.models import Activity
    data = dict(PARSED_ACTIVITY, garmin_activity_id=22222222)
    insert_activities(session, [data])
    session.flush()
    result = session.query(Activity).filter_by(garmin_activity_id=22222222).one()
    assert isinstance(result.activity_date, datetime.date)


def test_insert_activities_returns_count_of_inserted(session):
    from garmin.db_sync import insert_activities
    activities = [
        dict(PARSED_ACTIVITY, garmin_activity_id=33333333),
        dict(PARSED_ACTIVITY, garmin_activity_id=44444444),
    ]
    count = insert_activities(session, activities)
    session.flush()
    assert count == 2
