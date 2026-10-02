from math import cos, radians

METERS_PER_DEGREE_LAT = 110540.0
METERS_PER_DEGREE_LON = 111320.0


class LocalPlane:
    def __init__(self, lat0, lon0):
        self.lat0 = lat0
        self.lon0 = lon0
        self.lon_scale = METERS_PER_DEGREE_LON * cos(radians(lat0))

    def forward(self, lon, lat):
        return (
            (lon - self.lon0) * self.lon_scale,
            (lat - self.lat0) * METERS_PER_DEGREE_LAT,
        )

    def inverse(self, x, y):
        return (
            self.lon0 + x / self.lon_scale,
            self.lat0 + y / METERS_PER_DEGREE_LAT,
        )

    def forward_ring(self, coords):
        return [self.forward(lon, lat) for lon, lat in coords]

    def inverse_ring(self, coords):
        return [self.inverse(x, y) for x, y in coords]


def centred_on(bbox):
    south, west, north, east = bbox
    return LocalPlane((south + north) / 2.0, (west + east) / 2.0)
