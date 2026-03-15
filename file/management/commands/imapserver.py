import asyncio
import logging
import re
from datetime import datetime, timezone as dt_tz
from email.utils import format_datetime

from django.core.management.base import BaseCommand

logger = logging.getLogger('imapserver')

# IMAP flags mapping
FLAG_MAP = {
    '\\Seen': 'is_read',
    '\\Flagged': 'flagged',
    '\\Answered': 'answered',
    '\\Deleted': 'deleted',
    '\\Draft': 'draft',
}

SYSTEM_FLAGS = '\\Seen \\Answered \\Flagged \\Deleted \\Draft'


def _get_flags(email_obj):
    """Build IMAP flags string from email object."""
    flags = []
    if email_obj.is_read:
        flags.append('\\Seen')
    if email_obj.flagged:
        flags.append('\\Flagged')
    if email_obj.answered:
        flags.append('\\Answered')
    if email_obj.deleted:
        flags.append('\\Deleted')
    if email_obj.draft:
        flags.append('\\Draft')
    return ' '.join(flags)


def _parse_imap_args(line):
    """Parse IMAP command arguments, handling quoted strings and parenthesized lists."""
    tokens = []
    i = 0
    while i < len(line):
        if line[i] == ' ':
            i += 1
            continue
        elif line[i] == '"':
            end = line.index('"', i + 1)
            tokens.append(line[i + 1:end])
            i = end + 1
        elif line[i] == '(':
            end = line.index(')', i + 1)
            tokens.append(line[i + 1:end])
            i = end + 1
        elif line[i] == '[':
            end = line.index(']', i + 1)
            tokens.append(line[i:end + 1])
            i = end + 1
        else:
            end = i
            while end < len(line) and line[end] not in ' ()[]"':
                end += 1
            tokens.append(line[i:end])
            i = end
    return tokens


def _parse_sequence_set(seq_str, max_val):
    """Parse IMAP sequence set like '1:*', '1,3,5', '2:4'."""
    result = []
    for part in seq_str.split(','):
        part = part.strip()
        if ':' in part:
            start, end = part.split(':', 1)
            start = int(start) if start != '*' else max_val
            end = int(end) if end != '*' else max_val
            if start > end:
                start, end = end, start
            result.extend(range(start, end + 1))
        else:
            val = int(part) if part != '*' else max_val
            result.append(val)
    return result


class IMAPSession:
    """Represents one IMAP client session."""

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.user = None
        self.selected_mailbox = None
        self.selected_readonly = False
        self._emails_cache = []

    async def send(self, line):
        print(f'S: {line[:500]}')
        self.writer.write((line + '\r\n').encode('utf-8'))
        await self.writer.drain()

    async def run(self):
        await self.send('* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] Djancloud IMAP ready')

        try:
            while True:
                data = await self.reader.readline()
                if not data:
                    break
                line = data.decode('utf-8', errors='replace').strip()
                if not line:
                    continue

                print(f'C: {line}')
                await self.handle_line(line)
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            self.writer.close()

    async def handle_line(self, line):
        # IMAP commands are: TAG COMMAND [args...]
        parts = line.split(None, 2)
        if len(parts) < 2:
            return

        tag = parts[0]
        command = parts[1].upper()
        rest = parts[2] if len(parts) > 2 else ''

        handler = getattr(self, f'cmd_{command}', None)
        if handler:
            await handler(tag, rest)
        else:
            await self.send(f'{tag} BAD Unknown command {command}')

    # ─── IMAP Commands ───────────────────────────────────────

    async def cmd_CAPABILITY(self, tag, rest):
        await self.send('* CAPABILITY IMAP4rev1 AUTH=PLAIN')
        await self.send(f'{tag} OK CAPABILITY completed')

    async def cmd_NOOP(self, tag, rest):
        await self.send(f'{tag} OK NOOP completed')

    async def cmd_LOGOUT(self, tag, rest):
        await self.send('* BYE Djancloud IMAP server closing connection')
        await self.send(f'{tag} OK LOGOUT completed')
        self.writer.close()

    async def cmd_LOGIN(self, tag, rest):
        args = _parse_imap_args(rest)
        if len(args) < 2:
            await self.send(f'{tag} BAD LOGIN requires username and password')
            return

        username, password = args[0], args[1]

        from django.contrib.auth import authenticate
        from file.models import Mailbox
        user = await asyncio.to_thread(authenticate, username=username, password=password)
        if user is None:
            await self.send(f'{tag} NO LOGIN failed')
            return

        self.user = user
        await asyncio.to_thread(Mailbox.ensure_defaults, user)
        logger.info('User %s logged in', username)
        await self.send(f'{tag} OK LOGIN completed')

    async def cmd_AUTHENTICATE(self, tag, rest):
        # Minimal PLAIN support
        if rest.upper().strip() != 'PLAIN':
            await self.send(f'{tag} NO Unsupported mechanism')
            return

        await self.send('+')
        data = await self.reader.readline()
        if not data:
            await self.send(f'{tag} BAD Expected PLAIN data')
            return

        import base64
        try:
            decoded = base64.b64decode(data.strip()).decode('utf-8')
            # PLAIN format: \0username\0password
            parts = decoded.split('\0')
            if len(parts) == 3:
                username, password = parts[1], parts[2]
            else:
                await self.send(f'{tag} NO Invalid PLAIN data')
                return
        except Exception:
            await self.send(f'{tag} NO Invalid PLAIN data')
            return

        from django.contrib.auth import authenticate
        from file.models import Mailbox
        user = await asyncio.to_thread(authenticate, username=username, password=password)
        if user is None:
            await self.send(f'{tag} NO Authentication failed')
            return

        self.user = user
        await asyncio.to_thread(Mailbox.ensure_defaults, user)
        logger.info('User %s authenticated via PLAIN', username)
        await self.send(f'{tag} OK AUTHENTICATE completed')

    async def cmd_LIST(self, tag, rest):
        if not self.user:
            await self.send(f'{tag} NO Not authenticated')
            return

        args = _parse_imap_args(rest)
        reference = args[0] if args else ''
        pattern = args[1] if len(args) > 1 else '*'

        from file.models import Mailbox
        mailboxes = await asyncio.to_thread(
            lambda: list(Mailbox.objects.filter(owner=self.user).values_list('name', flat=True))
        )

        for name in mailboxes:
            # Match pattern (simple wildcard)
            if pattern == '*' or pattern == '%' or name == pattern:
                attrs = '\\HasNoChildren'
                if name == 'INBOX':
                    attrs = '\\HasNoChildren'
                elif name == 'Trash':
                    attrs = '\\HasNoChildren \\Trash'
                elif name == 'Sent':
                    attrs = '\\HasNoChildren \\Sent'
                elif name == 'Drafts':
                    attrs = '\\HasNoChildren \\Drafts'
                elif name == 'Junk':
                    attrs = '\\HasNoChildren \\Junk'
                await self.send(f'* LIST ({attrs}) "/" "{name}"')

        await self.send(f'{tag} OK LIST completed')

    async def cmd_LSUB(self, tag, rest):
        # Treat LSUB same as LIST
        await self.cmd_LIST(tag, rest)

    async def cmd_SELECT(self, tag, rest):
        await self._select(tag, rest, readonly=False)

    async def cmd_EXAMINE(self, tag, rest):
        await self._select(tag, rest, readonly=True)

    async def _select(self, tag, rest, readonly):
        if not self.user:
            await self.send(f'{tag} NO Not authenticated')
            return

        args = _parse_imap_args(rest)
        mailbox_name = args[0] if args else 'INBOX'

        from file.models import Mailbox, Email
        mb = await asyncio.to_thread(
            lambda: Mailbox.objects.filter(owner=self.user, name=mailbox_name).first()
        )
        if not mb:
            await self.send(f'{tag} NO Mailbox not found')
            return

        self.selected_mailbox = mb
        self.selected_readonly = readonly

        emails = await asyncio.to_thread(
            lambda: list(Email.objects.filter(mailbox=mb).order_by('imap_uid'))
        )
        self._emails_cache = emails

        total = len(emails)
        recent = 0
        unseen_idx = None
        for i, e in enumerate(emails, 1):
            if not e.is_read and unseen_idx is None:
                unseen_idx = i

        uid_validity = mb.id
        uid_next = (emails[-1].imap_uid + 1) if emails else 1

        await self.send(f'* {total} EXISTS')
        await self.send(f'* {recent} RECENT')
        await self.send(f'* FLAGS ({SYSTEM_FLAGS})')
        await self.send(f'* OK [PERMANENTFLAGS ({SYSTEM_FLAGS} \\*)] Flags permitted')
        if unseen_idx:
            await self.send(f'* OK [UNSEEN {unseen_idx}] First unseen')
        await self.send(f'* OK [UIDVALIDITY {uid_validity}] UIDs valid')
        await self.send(f'* OK [UIDNEXT {uid_next}] Predicted next UID')

        mode = 'READ-ONLY' if readonly else 'READ-WRITE'
        await self.send(f'{tag} OK [{mode}] SELECT completed')

    async def cmd_STATUS(self, tag, rest):
        if not self.user:
            await self.send(f'{tag} NO Not authenticated')
            return

        args = _parse_imap_args(rest)
        if len(args) < 2:
            await self.send(f'{tag} BAD STATUS requires mailbox and items')
            return

        mailbox_name = args[0]
        items_str = args[1].upper()

        from file.models import Mailbox, Email

        mb = await asyncio.to_thread(
            lambda: Mailbox.objects.filter(owner=self.user, name=mailbox_name).first()
        )
        if not mb:
            await self.send(f'{tag} NO Mailbox not found')
            return

        def _get_status():
            qs = Email.objects.filter(mailbox=mb)
            total = qs.count()
            unseen = qs.filter(is_read=False).count()
            last = qs.order_by('-imap_uid').values_list('imap_uid', flat=True).first()
            uid_next = (last or 0) + 1
            return total, unseen, mb.id, uid_next

        total, unseen, uid_validity, uid_next = await asyncio.to_thread(_get_status)

        parts = []
        if 'MESSAGES' in items_str:
            parts.append(f'MESSAGES {total}')
        if 'UNSEEN' in items_str:
            parts.append(f'UNSEEN {unseen}')
        if 'UIDVALIDITY' in items_str:
            parts.append(f'UIDVALIDITY {uid_validity}')
        if 'UIDNEXT' in items_str:
            parts.append(f'UIDNEXT {uid_next}')
        if 'RECENT' in items_str:
            parts.append('RECENT 0')

        await self.send(f'* STATUS "{mailbox_name}" ({" ".join(parts)})')
        await self.send(f'{tag} OK STATUS completed')

    async def cmd_FETCH(self, tag, rest):
        await self._fetch(tag, rest, use_uid=False)

    async def cmd_UID(self, tag, rest):
        """Handle UID FETCH, UID SEARCH, UID STORE, UID COPY."""
        parts = rest.split(None, 1)
        if not parts:
            await self.send(f'{tag} BAD UID requires subcommand')
            return

        subcmd = parts[0].upper()
        subrest = parts[1] if len(parts) > 1 else ''

        if subcmd == 'FETCH':
            await self._fetch(tag, subrest, use_uid=True)
        elif subcmd == 'SEARCH':
            await self._search(tag, subrest, use_uid=True)
        elif subcmd == 'STORE':
            await self._store(tag, subrest, use_uid=True)
        elif subcmd == 'COPY':
            await self._copy(tag, subrest, use_uid=True)
        else:
            await self.send(f'{tag} BAD Unknown UID subcommand')

    async def _refresh_cache(self):
        from file.models import Email
        if self.selected_mailbox:
            self._emails_cache = await asyncio.to_thread(
                lambda: list(Email.objects.filter(mailbox=self.selected_mailbox).order_by('imap_uid'))
            )

    def _resolve_sequence(self, seq_str, use_uid):
        """Resolve sequence set to list of (seq_num, email) tuples."""
        emails = self._emails_cache
        if not emails:
            return []

        if use_uid:
            uid_map = {e.imap_uid: (i + 1, e) for i, e in enumerate(emails)}
            max_uid = max(uid_map.keys()) if uid_map else 0
            uids = _parse_sequence_set(seq_str, max_uid)
            return [uid_map[u] for u in uids if u in uid_map]
        else:
            max_seq = len(emails)
            seqs = _parse_sequence_set(seq_str, max_seq)
            return [(s, emails[s - 1]) for s in seqs if 1 <= s <= max_seq]

    async def _fetch(self, tag, rest, use_uid):
        logger.debug('FETCH request: uid=%s rest=%r', use_uid, rest)
        if not self.selected_mailbox:
            await self.send(f'{tag} NO No mailbox selected')
            return

        await self._refresh_cache()

        parts = rest.split(None, 1)
        if len(parts) < 2:
            await self.send(f'{tag} BAD FETCH requires sequence and items')
            return

        seq_str = parts[0]
        items_raw = parts[1].strip()

        # Normalize macros
        items_upper = items_raw.upper()
        if items_upper == 'ALL':
            items_raw = '(FLAGS INTERNALDATE RFC822.SIZE ENVELOPE)'
        elif items_upper == 'FAST':
            items_raw = '(FLAGS INTERNALDATE RFC822.SIZE)'
        elif items_upper == 'FULL':
            items_raw = '(FLAGS INTERNALDATE RFC822.SIZE ENVELOPE BODY)'

        # Strip outer parens
        if items_raw.startswith('(') and items_raw.endswith(')'):
            items_raw = items_raw[1:-1]

        items = items_raw.upper()

        resolved = self._resolve_sequence(seq_str, use_uid)

        for seq_num, email_obj in resolved:
            parts_out = []

            if use_uid or 'UID' in items:
                parts_out.append(f'UID {email_obj.imap_uid}')

            if 'FLAGS' in items:
                parts_out.append(f'FLAGS ({_get_flags(email_obj)})')

            if 'INTERNALDATE' in items:
                dt = email_obj.received_at
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=dt_tz.utc)
                date_str = dt.strftime('%d-%b-%Y %H:%M:%S %z')
                parts_out.append(f'INTERNALDATE "{date_str}"')

            if 'RFC822.SIZE' in items:
                size = len(email_obj.raw_data.encode('utf-8'))
                parts_out.append(f'RFC822.SIZE {size}')

            if 'ENVELOPE' in items:
                env = self._build_envelope(email_obj)
                parts_out.append(f'ENVELOPE {env}')

            # Body/RFC822 fetch
            body_data = None
            if 'RFC822.HEADER' in items:
                header = self._extract_headers(email_obj)
                parts_out.append(f'RFC822.HEADER {{{len(header.encode("utf-8"))}}}')
                body_data = header
            elif 'RFC822.TEXT' in items:
                raw = email_obj.raw_data or ''
                idx = raw.find('\r\n\r\n')
                if idx == -1:
                    idx = raw.find('\n\n')
                text = raw[idx+2:] if idx >= 0 else raw
                parts_out.append(f'RFC822.TEXT {{{len(text.encode("utf-8"))}}}')
                body_data = text
            elif re.search(r'\bRFC822\b', items) and not re.search(r'\bRFC822\.', items):
                body_data = email_obj.raw_data
                parts_out.append(f'RFC822 {{{len(body_data.encode("utf-8"))}}}')
            elif 'BODY[]' in items or 'BODY.PEEK[]' in items:
                body_data = email_obj.raw_data
                peek = 'BODY.PEEK[]' in items
                parts_out.append(f'BODY[] {{{len(body_data.encode("utf-8"))}}}')
                if not peek and not email_obj.is_read:
                    email_obj.is_read = True
                    await asyncio.to_thread(
                        lambda e=email_obj: e.save(update_fields=['is_read'])
                    )
            elif 'BODY[HEADER]' in items or 'BODY.PEEK[HEADER]' in items:
                header = self._extract_headers(email_obj)
                parts_out.append(f'BODY[HEADER] {{{len(header.encode("utf-8"))}}}')
                body_data = header
            elif 'BODY[HEADER.FIELDS' in items or 'BODY.PEEK[HEADER.FIELDS' in items:
                # Parse requested fields
                match = re.search(r'HEADER\.FIELDS\s*\(([^)]+)\)', items)
                if match:
                    fields = match.group(1).split()
                    header = self._extract_header_fields(email_obj, fields)
                    key = f'BODY[HEADER.FIELDS ({match.group(1)})]'
                    parts_out.append(f'{key} {{{len(header.encode("utf-8"))}}}')
                    body_data = header
            elif 'BODY[TEXT]' in items or 'BODY.PEEK[TEXT]' in items:
                text = email_obj.body_text or email_obj.body_html or ''
                parts_out.append(f'BODY[TEXT] {{{len(text.encode("utf-8"))}}}')
                body_data = text
            elif re.search(r'BODY(?:\.PEEK)?\[(\d[\d.]*?)(?:\.MIME)?\]', items):
                # Handle BODY[1], BODY[1.1], BODY[2], BODY[1.MIME], etc.
                m = re.search(r'BODY(?:\.PEEK)?\[(\d[\d.]*?)(\.MIME)?\]', items)
                section = m.group(1)
                want_mime = m.group(2) is not None
                part_data = self._get_mime_part(email_obj, section, want_mime)
                key = f'BODY[{section}{".MIME" if want_mime else ""}]'
                if part_data is not None:
                    encoded = part_data.encode('utf-8') if isinstance(part_data, str) else part_data
                    parts_out.append(f'{key} {{{len(encoded)}}}')
                    body_data = part_data if isinstance(part_data, str) else part_data.decode('utf-8', errors='replace')
                else:
                    parts_out.append(f'{key} ""')
            elif 'BODYSTRUCTURE' in items or 'BODY' in re.split(r'[\s\[]', items):
                bs = self._build_bodystructure(email_obj)
                if 'BODYSTRUCTURE' in items:
                    parts_out.append(f'BODYSTRUCTURE {bs}')
                elif 'BODY' in items and not any(x in items for x in ['BODY[', 'BODY.PEEK']):
                    parts_out.append(f'BODY {bs}')

            if body_data is not None:
                # IMAP literal format: after {size}\r\n the literal bytes
                # follow immediately, then the closing paren for FETCH
                encoded_body = body_data.encode('utf-8') if isinstance(body_data, str) else body_data
                line = f'* {seq_num} FETCH ({" ".join(parts_out)}\r\n'
                logger.debug('FETCH response (literal): %s...', line[:200])
                self.writer.write(line.encode('utf-8'))
                self.writer.write(encoded_body)
                self.writer.write(b')\r\n')
                await self.writer.drain()
            else:
                resp = f'* {seq_num} FETCH ({" ".join(parts_out)})'
                logger.debug('FETCH response: %s', resp[:300])
                await self.send(resp)

        await self.send(f'{tag} OK FETCH completed')

    def _build_envelope(self, email_obj):
        """Build a simplified IMAP ENVELOPE response."""
        dt = email_obj.received_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_tz.utc)
        date_str = format_datetime(dt)
        subj = (email_obj.subject or '').replace('"', '\\"')
        from_addr = (email_obj.from_address or '').replace('"', '\\"')
        to_addr = (email_obj.to_addresses or '').replace('"', '\\"')
        msg_id = (email_obj.message_id or '').replace('"', '\\"')

        def _addr_list(addr_str):
            if not addr_str:
                return 'NIL'
            # Simplified: just return the address
            addr = addr_str.strip().replace('"', '\\"')
            name = 'NIL'
            mailbox = addr
            host = ''
            if '<' in addr and '>' in addr:
                name_part = addr.split('<')[0].strip()
                if name_part:
                    name = f'"{name_part}"'
                email_part = addr.split('<')[1].split('>')[0]
                if '@' in email_part:
                    mailbox, host = email_part.split('@', 1)
                else:
                    mailbox = email_part
            elif '@' in addr:
                mailbox, host = addr.split('@', 1)
            return f'(({name} NIL "{mailbox}" "{host}"))'

        from_list = _addr_list(from_addr)
        to_list = _addr_list(to_addr)

        return f'("{date_str}" "{subj}" {from_list} {from_list} {from_list} {to_list} NIL NIL NIL "{msg_id}")'

    def _extract_headers(self, email_obj):
        """Extract headers from raw email data."""
        raw = email_obj.raw_data
        # Headers end at first blank line
        idx = raw.find('\r\n\r\n')
        if idx == -1:
            idx = raw.find('\n\n')
        if idx >= 0:
            return raw[:idx] + '\r\n\r\n'
        return raw + '\r\n\r\n'

    def _extract_header_fields(self, email_obj, fields):
        """Extract specific header fields."""
        import email as email_mod
        import email.policy
        msg = email_mod.message_from_string(email_obj.raw_data, policy=email_mod.policy.default)
        result = []
        fields_lower = [f.lower() for f in fields]
        for key in msg.keys():
            if key.lower() in fields_lower:
                result.append(f'{key}: {msg[key]}')
        return '\r\n'.join(result) + '\r\n\r\n' if result else '\r\n'

    def _build_bodystructure(self, email_obj):
        """Build BODYSTRUCTURE response.

        If the email has raw_data, parse the actual MIME structure.
        Otherwise build a minimal structure from body_text/body_html.
        """
        if email_obj.raw_data:
            try:
                return self._bodystructure_from_raw(email_obj.raw_data)
            except Exception:
                pass

        has_text = bool(email_obj.body_text)
        has_html = bool(email_obj.body_html)
        has_attachments = email_obj.attachments.exists()

        text_part = None
        html_part = None
        if has_text:
            t = email_obj.body_text
            text_part = f'("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "8BIT" {len(t.encode("utf-8"))} {t.count(chr(10))})'
        if has_html:
            h = email_obj.body_html
            html_part = f'("TEXT" "HTML" ("CHARSET" "UTF-8") NIL NIL "8BIT" {len(h.encode("utf-8"))} {h.count(chr(10))})'

        if has_text and has_html:
            alt = f'({text_part} {html_part} "ALTERNATIVE")'
        elif has_html:
            alt = html_part
        else:
            alt = text_part or '("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "7BIT" 0 0)'

        if has_attachments:
            att_parts = []
            for att in email_obj.attachments.all():
                ct = (att.content_type or 'application/octet-stream').split('/')
                main = ct[0].upper() if ct else 'APPLICATION'
                sub = ct[1].upper() if len(ct) > 1 else 'OCTET-STREAM'
                att_parts.append(
                    f'("{main}" "{sub}" ("NAME" "{att.filename}") NIL NIL "BASE64" {att.size} NIL '
                    f'("ATTACHMENT" ("FILENAME" "{att.filename}")))'
                )
            return f'({alt} {" ".join(att_parts)} "MIXED")'

        return alt

    def _get_mime_part(self, email_obj, section, want_mime=False):
        """Get a specific MIME part by section number (e.g. '1', '1.1', '2').

        IMAP section numbering: for multipart/alternative with text+html,
        section 1 = text/plain, section 2 = text/html.
        For non-multipart messages, section 1 = the body.
        """
        if email_obj.raw_data:
            try:
                import email as email_mod
                msg = email_mod.message_from_string(
                    email_obj.raw_data, policy=email_mod.policy.default)
                part = self._navigate_to_part(msg, section)
                if part is None:
                    return ''
                if want_mime:
                    # Return MIME headers for this part
                    headers = []
                    for key, val in part.items():
                        headers.append(f'{key}: {val}')
                    return '\r\n'.join(headers) + '\r\n\r\n'
                payload = part.get_content()
                if isinstance(payload, bytes):
                    return payload.decode('utf-8', errors='replace')
                return payload or ''
            except Exception:
                pass

        # Fallback for emails without raw_data
        parts = [email_obj.body_text, email_obj.body_html]
        parts = [p for p in parts if p]
        try:
            idx = int(section.split('.')[0]) - 1
            if 0 <= idx < len(parts):
                return parts[idx]
        except (ValueError, IndexError):
            pass
        return ''

    def _navigate_to_part(self, msg, section):
        """Navigate MIME tree to find part at given section number."""
        indices = [int(x) for x in section.split('.')]
        current = msg
        for idx in indices:
            if current.is_multipart():
                payload = current.get_payload()
                if 1 <= idx <= len(payload):
                    current = payload[idx - 1]
                else:
                    return None
            else:
                if idx == 1:
                    return current
                return None
        return current

    def _bodystructure_from_raw(self, raw_data):
        """Parse raw MIME message into BODYSTRUCTURE."""
        import email as email_mod
        import email.policy
        msg = email_mod.message_from_string(raw_data, policy=email_mod.policy.default)
        return self._mime_to_bodystructure(msg)

    def _mime_to_bodystructure(self, part):
        """Recursively convert a MIME part to IMAP BODYSTRUCTURE string."""
        maintype = part.get_content_maintype().upper()
        subtype = part.get_content_subtype().upper()

        if part.is_multipart():
            children = ' '.join(self._mime_to_bodystructure(p) for p in part.get_payload())
            return f'({children} "{subtype}")'

        # Leaf part
        charset = part.get_content_charset() or 'UTF-8'
        encoding = (part.get('Content-Transfer-Encoding') or '7BIT').upper()
        disp = part.get_content_disposition()
        filename = part.get_filename()
        try:
            body = part.get_content()
            if isinstance(body, str):
                size = len(body.encode('utf-8'))
                lines = body.count('\n')
            else:
                size = len(body)
                lines = 0
        except Exception:
            size = 0
            lines = 0

        params = f'("CHARSET" "{charset.upper()}")' if maintype == 'TEXT' else 'NIL'
        disp_str = 'NIL'
        if disp == 'attachment' and filename:
            disp_str = f'("ATTACHMENT" ("FILENAME" "{filename}"))'

        bs = f'("{maintype}" "{subtype}" {params} NIL NIL "{encoding}" {size}'
        if maintype == 'TEXT':
            bs += f' {lines}'
        bs += f' NIL {disp_str})'
        return bs

    async def cmd_SEARCH(self, tag, rest):
        await self._search(tag, rest, use_uid=False)

    async def _search(self, tag, rest, use_uid):
        if not self.selected_mailbox:
            await self.send(f'{tag} NO No mailbox selected')
            return

        await self._refresh_cache()

        criteria = rest.upper().strip()
        emails = self._emails_cache
        results = []

        for i, e in enumerate(emails, 1):
            match = True
            if 'UNSEEN' in criteria and e.is_read:
                match = False
            if 'SEEN' in criteria and 'UNSEEN' not in criteria and not e.is_read:
                match = False
            if 'FLAGGED' in criteria and not e.flagged:
                match = False
            if 'DELETED' in criteria and 'UNDELETED' not in criteria and not e.deleted:
                match = False
            if 'UNDELETED' in criteria and e.deleted:
                match = False
            if 'ANSWERED' in criteria and not e.answered:
                match = False
            if 'DRAFT' in criteria and not e.draft:
                match = False

            if match:
                results.append(str(e.imap_uid) if use_uid else str(i))

        await self.send(f'* SEARCH {" ".join(results)}')
        await self.send(f'{tag} OK SEARCH completed')

    async def cmd_STORE(self, tag, rest):
        await self._store(tag, rest, use_uid=False)

    async def _store(self, tag, rest, use_uid):
        if not self.selected_mailbox or self.selected_readonly:
            await self.send(f'{tag} NO Cannot store in read-only mode')
            return

        await self._refresh_cache()

        parts = rest.split(None, 2)
        if len(parts) < 3:
            await self.send(f'{tag} BAD STORE requires sequence, action, flags')
            return

        seq_str = parts[0]
        action = parts[1].upper()
        flags_str = parts[2]

        if flags_str.startswith('(') and flags_str.endswith(')'):
            flags_str = flags_str[1:-1]

        flag_names = flags_str.split()
        silent = '.SILENT' in action

        resolved = self._resolve_sequence(seq_str, use_uid)

        for seq_num, email_obj in resolved:
            update_fields = []
            for flag in flag_names:
                flag_upper = flag.upper().replace('\\', '\\')
                # Normalize flag
                for imap_flag, model_field in FLAG_MAP.items():
                    if flag.upper() == imap_flag.upper():
                        if '+FLAGS' in action:
                            setattr(email_obj, model_field, True)
                        elif '-FLAGS' in action:
                            setattr(email_obj, model_field, False)
                        elif 'FLAGS' in action:
                            setattr(email_obj, model_field, True)
                        update_fields.append(model_field)

            if update_fields:
                await asyncio.to_thread(
                    lambda e=email_obj, uf=list(set(update_fields)): e.save(update_fields=uf)
                )

            if not silent:
                await self.send(f'* {seq_num} FETCH (FLAGS ({_get_flags(email_obj)}))')

        await self.send(f'{tag} OK STORE completed')

    async def cmd_EXPUNGE(self, tag, rest):
        if not self.selected_mailbox or self.selected_readonly:
            await self.send(f'{tag} NO Cannot expunge in read-only mode')
            return

        from file.models import Email
        deleted = await asyncio.to_thread(
            lambda: list(Email.objects.filter(
                mailbox=self.selected_mailbox, deleted=True
            ).order_by('imap_uid'))
        )

        # Calculate sequence numbers before deletion
        await self._refresh_cache()
        seq_map = {e.id: i + 1 for i, e in enumerate(self._emails_cache)}

        expunged_seqs = []
        for e in deleted:
            seq = seq_map.get(e.id)
            if seq:
                expunged_seqs.append(seq)

        # Delete from DB
        if deleted:
            ids = [e.id for e in deleted]
            await asyncio.to_thread(
                lambda: Email.objects.filter(id__in=ids).delete()
            )

        # Report in reverse order with adjusted sequence numbers
        offset = 0
        for seq in sorted(expunged_seqs):
            await self.send(f'* {seq - offset} EXPUNGE')
            offset += 1

        await self._refresh_cache()
        await self.send(f'{tag} OK EXPUNGE completed')

    async def cmd_CLOSE(self, tag, rest):
        if self.selected_mailbox and not self.selected_readonly:
            from file.models import Email
            await asyncio.to_thread(
                lambda: Email.objects.filter(
                    mailbox=self.selected_mailbox, deleted=True
                ).delete()
            )
        self.selected_mailbox = None
        self._emails_cache = []
        await self.send(f'{tag} OK CLOSE completed')

    async def _copy(self, tag, rest, use_uid):
        if not self.selected_mailbox:
            await self.send(f'{tag} NO No mailbox selected')
            return

        parts = rest.split(None, 1)
        if len(parts) < 2:
            await self.send(f'{tag} BAD COPY requires sequence and mailbox')
            return

        seq_str = parts[0]
        dest_args = _parse_imap_args(parts[1])
        dest_name = dest_args[0] if dest_args else parts[1].strip()

        from file.models import Mailbox, Email

        dest_mb = await asyncio.to_thread(
            lambda: Mailbox.objects.filter(owner=self.user, name=dest_name).first()
        )
        if not dest_mb:
            await self.send(f'{tag} NO [TRYCREATE] Destination mailbox not found')
            return

        await self._refresh_cache()
        resolved = self._resolve_sequence(seq_str, use_uid)

        for _, email_obj in resolved:
            await asyncio.to_thread(
                lambda e=email_obj: Email.objects.create(
                    mailbox=dest_mb,
                    message_id=e.message_id,
                    from_address=e.from_address,
                    to_addresses=e.to_addresses,
                    cc_addresses=e.cc_addresses,
                    subject=e.subject,
                    body_text=e.body_text,
                    body_html=e.body_html,
                    raw_data=e.raw_data,
                    is_read=e.is_read,
                )
            )

        await self.send(f'{tag} OK COPY completed')

    async def cmd_CREATE(self, tag, rest):
        if not self.user:
            await self.send(f'{tag} NO Not authenticated')
            return

        args = _parse_imap_args(rest)
        name = args[0] if args else rest.strip()

        from file.models import Mailbox
        _, created = await asyncio.to_thread(
            lambda: Mailbox.objects.get_or_create(owner=self.user, name=name)
        )
        if created:
            await self.send(f'{tag} OK CREATE completed')
        else:
            await self.send(f'{tag} NO Mailbox already exists')

    async def cmd_DELETE(self, tag, rest):
        if not self.user:
            await self.send(f'{tag} NO Not authenticated')
            return

        args = _parse_imap_args(rest)
        name = args[0] if args else rest.strip()

        from file.models import Mailbox, SYSTEM_MAILBOXES
        if name in SYSTEM_MAILBOXES:
            await self.send(f'{tag} NO Cannot delete system mailbox')
            return

        deleted = await asyncio.to_thread(
            lambda: Mailbox.objects.filter(owner=self.user, name=name).delete()
        )
        if deleted[0]:
            await self.send(f'{tag} OK DELETE completed')
        else:
            await self.send(f'{tag} NO Mailbox not found')

    async def cmd_RENAME(self, tag, rest):
        if not self.user:
            await self.send(f'{tag} NO Not authenticated')
            return

        args = _parse_imap_args(rest)
        if len(args) < 2:
            await self.send(f'{tag} BAD RENAME requires old and new name')
            return

        old_name, new_name = args[0], args[1]

        from file.models import Mailbox, SYSTEM_MAILBOXES
        if old_name in SYSTEM_MAILBOXES:
            await self.send(f'{tag} NO Cannot rename system mailbox')
            return

        def _do_rename():
            mb = Mailbox.objects.filter(owner=self.user, name=old_name).first()
            if not mb:
                return False
            mb.name = new_name
            mb.save(update_fields=['name'])
            return True

        ok = await asyncio.to_thread(_do_rename)
        if ok:
            await self.send(f'{tag} OK RENAME completed')
        else:
            await self.send(f'{tag} NO Mailbox not found')

    async def cmd_SUBSCRIBE(self, tag, rest):
        await self.send(f'{tag} OK SUBSCRIBE completed')

    async def cmd_UNSUBSCRIBE(self, tag, rest):
        await self.send(f'{tag} OK UNSUBSCRIBE completed')

    async def cmd_CHECK(self, tag, rest):
        await self.send(f'{tag} OK CHECK completed')

    async def cmd_NAMESPACE(self, tag, rest):
        await self.send('* NAMESPACE (("" "/")) NIL NIL')
        await self.send(f'{tag} OK NAMESPACE completed')

    async def cmd_ID(self, tag, rest):
        await self.send('* ID ("name" "Djancloud" "version" "1.0")')
        await self.send(f'{tag} OK ID completed')

    async def cmd_ENABLE(self, tag, rest):
        await self.send(f'{tag} OK ENABLE completed')

    async def cmd_IDLE(self, tag, rest):
        await self.send('+ idling')
        # Wait for DONE
        while True:
            data = await self.reader.readline()
            if not data:
                return
            line = data.decode('utf-8', errors='replace').strip()
            if line.upper() == 'DONE':
                break
        await self.send(f'{tag} OK IDLE terminated')

    async def cmd_APPEND(self, tag, rest):
        """Handle APPEND command: APPEND mailbox [flags] [date] {size}"""
        if not self.user:
            await self.send(f'{tag} NO Not authenticated')
            return

        args = _parse_imap_args(rest)
        if not args:
            await self.send(f'{tag} BAD APPEND requires arguments')
            return

        mailbox_name = args[0]

        # Find literal size {N}
        match = re.search(r'\{(\d+)\}', rest)
        if not match:
            await self.send(f'{tag} BAD APPEND requires literal')
            return

        size = int(match.group(1))
        await self.send('+ Ready for literal data')

        # Read exactly `size` bytes
        raw_bytes = await self.reader.readexactly(size)
        # Read trailing CRLF
        await self.reader.readline()

        raw_str = raw_bytes.decode('utf-8', errors='replace')

        import email as email_mod
        import email.policy
        msg = email_mod.message_from_string(raw_str, policy=email_mod.policy.default)

        from file.models import Mailbox, Email
        mb = await asyncio.to_thread(
            lambda: Mailbox.objects.filter(owner=self.user, name=mailbox_name).first()
        )
        if not mb:
            await self.send(f'{tag} NO [TRYCREATE] Mailbox not found')
            return

        await asyncio.to_thread(
            lambda: Email.objects.create(
                mailbox=mb,
                message_id=msg.get('Message-ID', ''),
                from_address=msg.get('From', ''),
                to_addresses=msg.get('To', ''),
                cc_addresses=msg.get('Cc', ''),
                subject=msg.get('Subject', ''),
                body_text=self._get_text_body(msg),
                body_html=self._get_html_body(msg),
                raw_data=raw_str,
            )
        )

        await self.send(f'{tag} OK APPEND completed')

    @staticmethod
    def _get_text_body(msg):
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode('utf-8', errors='replace')
        else:
            if msg.get_content_type() == 'text/plain':
                payload = msg.get_payload(decode=True)
                if payload:
                    return payload.decode('utf-8', errors='replace')
        return ''

    @staticmethod
    def _get_html_body(msg):
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode('utf-8', errors='replace')
        else:
            if msg.get_content_type() == 'text/html':
                payload = msg.get_payload(decode=True)
                if payload:
                    return payload.decode('utf-8', errors='replace')
        return ''


async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    logger.info('Connection from %s', addr)
    session = IMAPSession(reader, writer)
    await session.run()
    logger.info('Connection closed from %s', addr)


class Command(BaseCommand):
    help = 'Run an IMAP4rev1 server that serves emails from the database'

    def add_arguments(self, parser):
        parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
        parser.add_argument('--port', type=int, default=1143, help='Port to listen on')

    def handle(self, *args, **options):
        host = options['host']
        port = options['port']

        self.stdout.write(self.style.SUCCESS(
            f'Starting IMAP server on {host}:{port}'
        ))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        server = loop.run_until_complete(
            asyncio.start_server(handle_client, host, port)
        )

        self.stdout.write(self.style.SUCCESS(f'IMAP server listening on {host}:{port}'))

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.close()
            loop.run_until_complete(server.wait_closed())
            loop.close()
            self.stdout.write('IMAP server stopped.')
