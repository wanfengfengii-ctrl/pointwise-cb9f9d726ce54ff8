from gridledger.windows.model import ClippedSegment

def clip_segments(records, a, b):
    segments = [ClippedSegment(r, max(a, r.start), min(b, r.end))
                for r in records if r.start < b and r.end > a]
    return tuple(sorted(segments, key=lambda s: (s.start, s.end, s.record.source_id)))

def require_exact_coverage(segments, a, b):
    cursor = a
    for segment in segments:
        if segment.start != cursor or segment.end <= segment.start:
            raise ValueError("flux window has gap or overlap")
        cursor = segment.end
    if cursor != b:
        raise ValueError("incomplete flux window")

def iter_common_intervals(left, right):
    i = j = 0
    while i < len(left) and j < len(right):
        x, y = left[i], right[j]
        start, end = max(x.start, y.start), min(x.end, y.end)
        if start < end:
            yield start, end, x.record, y.record
        if x.end <= y.end:
            i += 1
        if y.end <= x.end:
            j += 1
