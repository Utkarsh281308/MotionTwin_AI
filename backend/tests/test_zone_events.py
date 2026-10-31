from app.schemas.models import Point, Track, TrackPoint, Zone
from app.vision.zone_events import extract_zone_events, point_in_polygon

SQUARE = [Point(x=0, y=0), Point(x=10, y=0), Point(x=10, y=10), Point(x=0, y=10)]


def test_point_in_polygon():
    assert point_in_polygon(5, 5, SQUARE)
    assert not point_in_polygon(15, 5, SQUARE)


def test_enter_exit_times():
    # x moves -5..19 one unit per frame; inside the square for x in 0..9 -> frames 5..14
    track = Track(track_id=1, points=[TrackPoint(frame=f, x=f - 5 + 0.5, y=5) for f in range(25)])
    zone = Zone(id="z", name="Z", polygon=SQUARE)
    [e] = extract_zone_events([track], [zone], fps=10)
    assert e.enter_time == 0.5 and e.exit_time == 1.4
    assert not e.censored


def test_censored_when_track_starts_inside():
    track = Track(track_id=1, points=[TrackPoint(frame=f, x=5 + f, y=5) for f in range(10)])
    [e] = extract_zone_events([track], [Zone(id="z", name="Z", polygon=SQUARE)], fps=10)
    assert e.censored
