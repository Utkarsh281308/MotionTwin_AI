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


def test_parse_sam_output_box_centres():
    from app.vision.meta_sam import parse_sam_output
    mask = "<|mask;x=0;y=0;data=27,60,~!!!!M!0c[0o91w?q1!pIH4pPRVp2B3'7`e.ioeAf6-k/#Xd8%dX9x(|>"
    text = (f"<0f>0<|box;x1=10;y1=20;x2=29;y2=39;w=320;h=334|>{mask}\n"
            f"<1f>0<|box;x1=20;y1=20;x2=39;y2=39;w=320;h=334|>{mask}\n")
    [track] = parse_sam_output(text)
    assert [p.frame for p in track.points] == [0, 1]
    assert (track.points[0].x, track.points[0].y) == (20, 30)
