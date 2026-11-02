from app.vision.tracker import greedy_track, split_at_jumps
from app.schemas.models import Track, TrackPoint


def test_queue_handover_keeps_ids():
    # box 0 at the queue front steps into the station (+45px/frame); box 1 then moves up 32px
    detections = {0: [(440, 180), (408, 180)], 1: [(485, 180), (408, 180)],
                  2: [(530, 180), (408, 180)], 3: [(530, 180), (440, 180)]}
    tracks = greedy_track(detections, max_dist=60)
    assert len(tracks) == 2
    assert [p.x for p in tracks[0].points] == [440, 485, 530, 530]
    assert [p.x for p in tracks[1].points] == [408, 408, 408, 440]


def test_new_object_starts_new_track():
    tracks = greedy_track({0: [(10, 10)], 1: [(15, 10), (300, 10)]}, max_dist=60)
    assert len(tracks) == 2


def test_split_at_jumps():
    t = Track(track_id=0, points=[TrackPoint(frame=f, x=x, y=0) for f, x in enumerate([600, 620, 640, 120, 140])])
    assert [len(s.points) for s in split_at_jumps([t])] == [3, 2]
