import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task
def send_email_task(from_address, to_addresses, cc_addresses, subject,
                    body_text, body_html, attachments=None):
    """Send an email via SMTP relay in background.

    attachments: list of dicts with keys: filename, content_type, data (base64 encoded)
    """
    import base64

    smtp_host = getattr(settings, 'SMTP_RELAY_HOST', None)
    smtp_port = getattr(settings, 'SMTP_RELAY_PORT', 587)
    smtp_user = getattr(settings, 'SMTP_RELAY_USER', None)
    smtp_pass = getattr(settings, 'SMTP_RELAY_PASSWORD', None)
    smtp_tls = getattr(settings, 'SMTP_RELAY_USE_TLS', True)

    if not smtp_host:
        logger.warning("No SMTP_RELAY_HOST configured, cannot send email")
        return False

    attachments = attachments or []
    has_attachments = len(attachments) > 0

    if has_attachments:
        msg = MIMEMultipart('mixed')
        body_part = MIMEMultipart('alternative')
    else:
        msg = MIMEMultipart('alternative')
        body_part = msg

    msg['From'] = from_address
    msg['To'] = to_addresses
    if cc_addresses:
        msg['Cc'] = cc_addresses
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid()

    body_part.attach(MIMEText(body_text, 'plain', 'utf-8'))
    body_part.attach(MIMEText(body_html, 'html', 'utf-8'))

    if has_attachments:
        msg.attach(body_part)

    for att in attachments:
        maintype, subtype = att['content_type'].split('/', 1) if '/' in att['content_type'] else ('application', 'octet-stream')
        part = MIMEBase(maintype, subtype)
        part.set_payload(base64.b64decode(att['data']))
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment', filename=att['filename'])
        msg.attach(part)

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        if smtp_tls:
            server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        all_recipients = [a.strip() for a in to_addresses.split(',')]
        if cc_addresses:
            all_recipients += [a.strip() for a in cc_addresses.split(',')]
        server.sendmail(from_address, all_recipients, msg.as_string())
        server.quit()
        logger.info("Email sent from %s to %s", from_address, to_addresses)
        return True
    except Exception as e:
        logger.error("Failed to send email from %s to %s: %s", from_address, to_addresses, e)
        raise


@shared_task
def send_event_invitation(event_id, invitee_id):
    """Send a calendar invitation email."""
    from .models import Event, EventInvitee

    try:
        invitee = EventInvitee.objects.select_related('event__calendar__owner').get(pk=invitee_id)
    except EventInvitee.DoesNotExist:
        return

    if invitee.notified:
        return

    event = invitee.event
    organizer = event.calendar.owner
    from_address = organizer.email or f'{organizer.username}@localhost'

    smtp_host = getattr(settings, 'SMTP_RELAY_HOST', None)
    smtp_port = getattr(settings, 'SMTP_RELAY_PORT', 587)
    smtp_user = getattr(settings, 'SMTP_RELAY_USER', None)
    smtp_pass = getattr(settings, 'SMTP_RELAY_PASSWORD', None)
    smtp_tls = getattr(settings, 'SMTP_RELAY_USE_TLS', True)

    if not smtp_host:
        logger.warning("No SMTP_RELAY_HOST configured, cannot send invitation")
        invitee.notified = True
        invitee.save(update_fields=['notified'])
        return

    # Build email
    start_str = event.dtstart.strftime('%A %d %B %Y %H:%M') if event.dtstart else 'TBD'
    end_str = event.dtend.strftime('%H:%M') if event.dtend else ''
    time_str = f"{start_str} - {end_str}" if end_str else start_str

    subject = f"Invitation: {event.summary or '(No title)'}"
    body_text = (
        f"You have been invited to an event.\n\n"
        f"Title: {event.summary or '(No title)'}\n"
        f"When: {time_str}\n"
    )
    if event.location:
        body_text += f"Where: {event.location}\n"
    if event.description:
        body_text += f"\n{event.description}\n"
    body_text += f"\nOrganizer: {organizer.get_full_name() or organizer.username} <{from_address}>\n"

    body_html = (
        f"<h2>{event.summary or '(No title)'}</h2>"
        f"<p><strong>When:</strong> {time_str}</p>"
    )
    if event.location:
        body_html += f"<p><strong>Where:</strong> {event.location}</p>"
    if event.description:
        body_html += f"<p>{event.description}</p>"
    body_html += f"<p><strong>Organizer:</strong> {organizer.get_full_name() or organizer.username}</p>"

    msg = MIMEMultipart('alternative')
    msg['From'] = from_address
    msg['To'] = invitee.email
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid()
    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        if smtp_tls:
            server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.sendmail(from_address, [invitee.email], msg.as_string())
        server.quit()
        invitee.notified = True
        invitee.save(update_fields=['notified'])
        logger.info("Invitation sent for event %s to %s", event.summary, invitee.email)
    except Exception as e:
        logger.error("Failed to send invitation to %s: %s", invitee.email, e)
        raise


@shared_task
def send_out_of_office_reply(user_id, sender_email, original_subject):
    """Send an out-of-office auto-reply if conditions are met."""
    from .models import User, OutOfOffice, OutOfOfficeReply

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    try:
        ooo = user.out_of_office
    except OutOfOffice.DoesNotExist:
        return

    if not ooo.is_active():
        return

    # Don't reply to noreply, mailer-daemon, etc.
    sender_lower = sender_email.lower()
    skip_prefixes = ['noreply@', 'no-reply@', 'mailer-daemon@', 'postmaster@']
    if any(sender_lower.startswith(p) for p in skip_prefixes):
        return

    # Check if we already replied to this sender
    _, created = OutOfOfficeReply.objects.get_or_create(
        user=user, sender_email=sender_lower)
    if not created:
        return

    from_address = user.email or f'{user.username}@localhost'

    smtp_host = getattr(settings, 'SMTP_RELAY_HOST', None)
    smtp_port = getattr(settings, 'SMTP_RELAY_PORT', 587)
    smtp_user = getattr(settings, 'SMTP_RELAY_USER', None)
    smtp_pass = getattr(settings, 'SMTP_RELAY_PASSWORD', None)
    smtp_tls = getattr(settings, 'SMTP_RELAY_USE_TLS', True)

    if not smtp_host:
        logger.warning("No SMTP_RELAY_HOST configured, cannot send OOO reply")
        return

    msg = MIMEMultipart('alternative')
    msg['From'] = from_address
    msg['To'] = sender_email
    msg['Subject'] = ooo.subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid()
    msg['Auto-Submitted'] = 'auto-replied'
    msg['X-Auto-Response-Suppress'] = 'All'

    msg.attach(MIMEText(ooo.body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        if smtp_tls:
            server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.sendmail(from_address, [sender_email], msg.as_string())
        server.quit()
        logger.info("OOO reply sent from %s to %s", from_address, sender_email)
    except Exception as e:
        logger.error("Failed to send OOO reply from %s to %s: %s", from_address, sender_email, e)
        raise
