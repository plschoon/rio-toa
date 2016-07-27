import re
import datetime
import numpy as np


def parse_utc_string(collected_date, collected_time_utc):
    """
    Given a string in the format:
        YYYY-MM-DD HH:MM:SS.SSSSSSSSZ
    Parse and convert into a datetime object
    Fractional seconds are ignored

    Parameters
    -----------
    collected_date_utc: str
        Format: YYYY-MM-DD
    collected_time: str
        Format: HH:MM:SS.SSSSSSSSZ

    Returns
    --------
    datetime object
        parsed scene center time
    """
    utcstr = collected_date + ' ' + collected_time_utc

    if not re.match(r'\d{4}\-\d{2}\-\d{2}\ \d{2}\:\d{2}\:\d{2}\.\d+Z',
                    utcstr):
        raise ValueError("%s is an invalid utc time" % utcstr)

    return datetime.datetime.strptime(
        utcstr.split(".")[0],
        "%Y-%m-%d %H:%M:%S")


def time_to_dec_hour(parsedtime):
    """
    Calculate the decimal hour from a datetime object

    Parameters
    -----------
    parsedtime: datetime object

    Returns
    --------
    decimal hour: float
        time in decimal hours
    """
    return (parsedtime.hour +
            (parsedtime.minute / 60.0) +
            (parsedtime.second / 60.0 ** 2)
            )


def calculate_declination(d):
    """
    Calculate the declination of the sun in radians based on a given day.
    As reference +23.26 degrees at the northern summer solstice, -23.26
    degrees at the southern summer solstice.
    See: https://en.wikipedia.org/wiki/Position_of_the_Sun#Calculations

    Parameters
    -----------
    d: int
        days from midnight on January 1st

    Returns
    --------
    declination in radians: float
        the declination on day d

    """
    return np.arcsin(
                     np.sin(np.deg2rad(23.45)) *
                     np.sin(np.deg2rad(360. / 365.) *
                            (d - 81))
                    )


def solar_angle(day, utc_hour, longitude):
    """
    Given a day, utc decimal hour, and longitudes, compute the solar angle
    for these longitudes

    Parameters
    -----------
    day: int
        days of the year with jan 1 as day = 1
    utc_hour: float
        decimal hour of the day in utc time to compute solar angle for
    longitude: ndarray or float
        longitude of the point(s) to compute solar angle for

    Returns
    --------
    solar angle in degrees for these longitudes
    """
    localtime = (longitude / 180.0) * 12 + utc_hour

    lstm = 15 * (localtime - utc_hour)

    B = np.deg2rad((360. / 365.) * (day - 81))

    eot = (9.87 *
           np.sin(2 * B) -
           7.53 * np.cos(B) -
           1.5 * np.sin(B))

    return 15 * (localtime +
                 (4 * (longitude - lstm) + eot) / 60.0 - 12)


def _calculate_sun_elevation(longitude, latitude, declination, day, utc_hour):
    """
    Calculates the solar elevation angle
    https://en.wikipedia.org/wiki/Solar_zenith_angle

    Parameters
    -----------
    longitude: ndarray or float
        longitudes of the point(s) to compute solar angle for
    latitude: ndarray or float
        latitudes of the point(s) to compute solar angle for
    declination: float
        declination of the sun in radians
    day: int
        days of the year with jan 1 as day = 1
    utc_hour: float
        decimal hour from a datetime object

    Returns
    --------
    the solar elevation angle in degrees
    """
    hour_angle = np.deg2rad(solar_angle(day, utc_hour, longitude))

    latitude = np.deg2rad(latitude)

    return np.rad2deg(np.arcsin(
        np.sin(declination) *
        np.sin(latitude) +
        np.cos(declination) *
        np.cos(latitude) *
        np.cos(hour_angle)
    ))


def _make_lat_lng_array(shape, resolution, lower_left):
    xCell, yCell = resolution
    left, bottom = lower_left

    lat, lng = np.indices(shape)

    return ((lng.astype(np.float32) * xCell) + left + (xCell / 2.0),
            (lat.astype(np.float32) * yCell) + bottom + (yCell / 2.0))


def sun_elevation(bounds, shape, date_collected, time_collected_utc):
    """
    Given a raster's bounds + dimensions, calculate the
    sun elevation angle in degrees for each input pixel
    based on metadata from a Landsat MTL file

    Parameters
    -----------
    bounds: BoundingBox
        bounding box of the input raster
    shape: tuple
        tuple of (rows, cols) or (depth, rows, cols) for input raster
    collected_date_utc: str
        Format: YYYY-MM-DD
    collected_time: str
        Format: HH:MM:SS.SSSSSSSSZ

    Returns
    --------
    ndarray
        ndarray with shape = (rows, cols) with sun elevation
        in degrees calculated for each pixel
    """
    utc_time = parse_utc_string(date_collected, time_collected_utc)

    if len(shape) == 3:
        _, rows, cols = shape
    else:
        rows, cols = shape

    xCell = (bounds.right - bounds.left) / float(cols)
    yCell = (bounds.top - bounds.bottom) / float(rows)

    lng, lat = _make_lat_lng_array((rows, cols),
                                   (xCell, yCell),
                                   (bounds.left, bounds.bottom))

    decimal_hour = time_to_dec_hour(utc_time)

    declination = calculate_declination(utc_time.timetuple().tm_yday)

    return _calculate_sun_elevation(lng, lat, declination,
                                    utc_time.timetuple().tm_yday,
                                    decimal_hour)
