from fractions import Fraction
from gridledger.windows.model import SourceContribution

def integrate_segment(segment, face_id):
    duration = segment.end - segment.start
    if duration <= 0:
        raise ValueError("empty contribution")
    return SourceContribution(segment.record, face_id, segment.start, segment.end,
                              duration, segment.record.rate * duration)

def validate_contribution_total(contributions, total):
    for c in contributions:
        if not (c.record.start <= c.start < c.end <= c.record.end):
            raise ValueError("contribution outside source interval")
        if c.duration != c.end - c.start or c.integral != c.record.rate * c.duration:
            raise ValueError("source evidence differs from integral")
    if sum((c.integral for c in contributions), Fraction(0)) != total:
        raise ValueError("face total differs from evidence")

def integrate_face(segments, face_id):
    contributions = tuple(integrate_segment(s, face_id) for s in segments)
    total = sum((c.integral for c in contributions), Fraction(0))
    validate_contribution_total(contributions, total)
    return contributions
