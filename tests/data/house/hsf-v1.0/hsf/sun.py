"""Where the sun is (NOAA formulas) – the same formulas as House Planner's ``sunPosition`` (src/sun.js).

The format does not make the reader work the sun out: House Planner writes each moment's azimuth, elevation and
direction, and Fresing Render bakes with them. The checker uses this only to warn when a moment's sun does not fit its
date, clock time, UTC offset and place (a time-zone mistake, for example).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone


def utc_moment(date: str, time: str, utc_offset: str) -> datetime:
    sign = 1 if utc_offset[0] == "+" else -1
    hh, mm = utc_offset[1:].split(":")
    off = timedelta(hours=int(hh), minutes=int(mm)) * sign
    local = datetime.fromisoformat(f"{date}T{time}:00")
    return (local - off).replace(tzinfo=timezone.utc)


def sun_position(lat: float, lon: float, when: datetime) -> tuple[float, float]:
    """(azimuth degrees clockwise from north, elevation degrees) at a moment in UTC."""
    rad = math.pi / 180
    doy = when.timetuple().tm_yday
    hour = when.hour + when.minute / 60 + when.second / 3600
    g = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                    - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    ha = ((hour * 60 + eqt + 4 * lon) / 4 - 180) * rad
    phi = lat * rad
    cos_z = math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(ha)
    el = 90 - math.acos(max(-1.0, min(1.0, cos_z))) / rad
    az = (math.atan2(math.sin(ha), math.cos(ha) * math.sin(phi) - math.tan(decl) * math.cos(phi)) / rad + 180
          + 360) % 360
    return az, el
