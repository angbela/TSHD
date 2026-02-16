"""
Segmented navigation channel model.

We model the channel as equal-length segments along a 1D axis.
Segment 1 is the nearest reference point (distance 0 along-channel).
Distance to dumping area (DA) is derived from the current segment index:
    distance_nm = (segment_index - 1) * segment_length_nm
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class SegmentAllocation:
    segment_index: int  # 1-based
    volume_m3: float
    distance_to_da_nm: float


class SegmentManager:
    def __init__(self, segment_volumes_m3: List[float], segment_length_nm: float):
        if segment_length_nm <= 0:
            raise ValueError("segment_length_nm must be > 0")
        self.segment_length_nm = float(segment_length_nm)
        # store as floats, 1-based concept but list is 0-based
        self.remaining_m3 = [max(0.0, float(v)) for v in segment_volumes_m3]

    def total_remaining(self) -> float:
        return float(sum(self.remaining_m3))

    def next_segment_with_work(self) -> Optional[int]:
        for i, v in enumerate(self.remaining_m3):
            if v > 0:
                return i + 1
        return None

    def allocate(self, requested_m3: float) -> Optional[SegmentAllocation]:
        """
        Allocate up to requested_m3 from the lowest-index segment with remaining work.
        Returns None if no remaining work.
        """
        if requested_m3 <= 0:
            return None
        seg_idx = self.next_segment_with_work()
        if seg_idx is None:
            return None

        remaining = self.remaining_m3[seg_idx - 1]
        take = min(float(requested_m3), float(remaining))
        self.remaining_m3[seg_idx - 1] = float(remaining - take)

        distance_nm = (seg_idx - 1) * self.segment_length_nm
        return SegmentAllocation(segment_index=seg_idx, volume_m3=take, distance_to_da_nm=distance_nm)

