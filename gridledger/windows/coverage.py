from gridledger.windows.model import ClippedSegment

def clip_segments(records, a, b):
    segments = [ClippedSegment(r, max(a, r.start), min(b, r.end))
                for r in records if r.start < b and r.end > a]
    return tuple(sorted(segments, key=lambda s: (s.start, s.end, s.record.source_id)))

def merge_continuous(segments):
    merged = []
    for segment in segments:
        if (merged and merged[-1].record.source_id == segment.record.source_id
                and merged[-1].end == segment.start):
            merged[-1] = ClippedSegment(segment.record, merged[-1].start, segment.end)
        else:
            merged.append(segment)
    return merged

def face_window_segments(fragments, a, b):
    ordered = sorted((ClippedSegment(f.record, f.start, f.end) for f in fragments),
                     key=lambda s: (s.start, s.end, s.record.source_id))
    segments = [ClippedSegment(s.record, max(a, s.start), min(b, s.end))
                for s in merge_continuous(ordered) if s.start < b and s.end > a]
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
