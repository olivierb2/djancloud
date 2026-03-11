"""Utility functions for parsing and generating iCalendar and vCard data."""
import hashlib
from datetime import datetime, date, timezone as dt_timezone
from django.utils import timezone
import icalendar
import vobject


def parse_icalendar(ical_string):
    """Parse an iCalendar string and extract VEVENT fields.

    Returns a dict with extracted fields for database storage.
    """
    cal = icalendar.Calendar.from_ical(ical_string)
    result = {}

    for component in cal.walk():
        if component.name == 'VEVENT':
            result['uid'] = str(component.get('uid', ''))
            result['summary'] = str(component.get('summary', '')) or None
            result['description'] = str(component.get('description', '')) or None
            result['location'] = str(component.get('location', '')) or None

            dtstart = component.get('dtstart')
            if dtstart:
                dt = dtstart.dt
                if isinstance(dt, date) and not isinstance(dt, datetime):
                    result['dtstart'] = datetime.combine(dt, datetime.min.time(), tzinfo=dt_timezone.utc)
                    result['all_day'] = True
                else:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=dt_timezone.utc)
                    result['dtstart'] = dt
                    result['all_day'] = False

            dtend = component.get('dtend')
            if dtend:
                dt = dtend.dt
                if isinstance(dt, date) and not isinstance(dt, datetime):
                    result['dtend'] = datetime.combine(dt, datetime.min.time(), tzinfo=dt_timezone.utc)
                else:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=dt_timezone.utc)
                    result['dtend'] = dt

            rrule = component.get('rrule')
            if rrule:
                result['recurrence_rule'] = rrule.to_ical().decode('utf-8')

            break  # Only process first VEVENT

    return result


def generate_etag(uid):
    """Generate an ETag for a calendar/contact resource."""
    return hashlib.md5(f"{uid}-{timezone.now().timestamp()}".encode()).hexdigest()


def parse_vcard(vcard_string):
    """Parse a vCard string and extract fields for database storage.

    Returns a dict with extracted fields.
    """
    vcard = vobject.readOne(vcard_string)
    result = {}

    result['uid'] = str(getattr(vcard, 'uid', None).value) if hasattr(vcard, 'uid') else ''

    if hasattr(vcard, 'fn'):
        result['fn'] = str(vcard.fn.value)

    if hasattr(vcard, 'n'):
        result['n'] = str(vcard.n.value)

    if hasattr(vcard, 'email'):
        result['email'] = str(vcard.email.value)

    if hasattr(vcard, 'tel'):
        result['tel'] = str(vcard.tel.value)

    if hasattr(vcard, 'org'):
        org_value = vcard.org.value
        if isinstance(org_value, list):
            result['org'] = ';'.join(org_value)
        else:
            result['org'] = str(org_value)

    return result


def validate_icalendar(ical_string):
    """Validate that a string is valid iCalendar data containing a VEVENT.

    Returns (is_valid, error_message).
    """
    try:
        cal = icalendar.Calendar.from_ical(ical_string)
        has_vevent = False
        for component in cal.walk():
            if component.name == 'VEVENT':
                if not component.get('uid'):
                    return False, "VEVENT must have a UID"
                has_vevent = True
                break
        if not has_vevent:
            return False, "No VEVENT component found"
        return True, None
    except Exception as e:
        return False, str(e)


def validate_vcard(vcard_string):
    """Validate that a string is valid vCard data.

    Returns (is_valid, error_message).
    """
    try:
        vcard = vobject.readOne(vcard_string)
        if not hasattr(vcard, 'fn'):
            return False, "vCard must have a FN property"
        return True, None
    except Exception as e:
        return False, str(e)


def wrap_vevent_in_vcalendar(vevent_data):
    """Ensure iCalendar data is wrapped in a VCALENDAR container."""
    if 'BEGIN:VCALENDAR' in vevent_data:
        return vevent_data
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//DjanCloud//CalDAV//EN\r\n"
        f"{vevent_data}\r\n"
        "END:VCALENDAR\r\n"
    )
