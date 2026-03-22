import logging

from twisted.internet import reactor, protocol
from twisted.internet.endpoints import TCP4ServerEndpoint

from ldaptor.protocols.ldap.ldapserver import LDAPServer
from ldaptor.protocols import pureldap
from ldaptor.protocols.ldap import distinguishedname

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import check_password

logger = logging.getLogger('ldapserver')

from django.conf import settings as django_settings

BASE_DN = getattr(django_settings, 'LDAP_BASE_DN', 'dc=djancloud,dc=local')
USERS_DN = f'ou=Users,{BASE_DN}'
CONTACTS_DN = f'ou=Contacts,{BASE_DN}'


def dn_str(dn):
    if isinstance(dn, bytes):
        return dn.decode('utf-8')
    return str(dn)


class DjancloudLDAPServer(LDAPServer):
    """Read-only LDAP server backed by Django models."""

    def __init__(self):
        LDAPServer.__init__(self)
        self.bound_user = None

    def handle_LDAPBindRequest(self, request, controls, reply):
        bind_dn = dn_str(request.dn)
        bind_pw = request.auth.decode('utf-8') if request.auth else ''

        # Anonymous bind
        if not bind_dn or not bind_pw:
            self.bound_user = None
            return pureldap.LDAPBindResponse(resultCode=0)

        # Try to authenticate against Django users
        # Expected DN: uid=username,ou=Users,dc=djancloud,dc=local
        import django
        django.setup()
        from file.models import User

        try:
            parts = distinguishedname.DistinguishedName(stringValue=bind_dn)
            rdn = str(parts.listOfRDNs[0])
            if rdn.lower().startswith('uid='):
                username = rdn.split('=', 1)[1]
            else:
                return pureldap.LDAPBindResponse(resultCode=49, errorMessage='Invalid DN')
        except Exception:
            return pureldap.LDAPBindResponse(resultCode=49, errorMessage='Invalid DN')

        try:
            user = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist:
            return pureldap.LDAPBindResponse(resultCode=49, errorMessage='Invalid credentials')

        if not check_password(bind_pw, user.password):
            # Also try AppToken
            from file.models import AppToken
            if not AppToken.objects.filter(user=user, token=bind_pw).exists():
                return pureldap.LDAPBindResponse(resultCode=49, errorMessage='Invalid credentials')

        self.bound_user = user
        logger.info("LDAP bind: %s", username)
        return pureldap.LDAPBindResponse(resultCode=0)

    def handle_LDAPSearchRequest(self, request, controls, reply):
        import django
        django.setup()
        from file.models import User, Contact, AddressBook, AddressBookShare

        base_dn = dn_str(request.baseObject).lower()
        scope = request.scope
        filter_obj = request.filter

        results = []

        # Search base DN - return the root entry
        if base_dn == BASE_DN.lower() or base_dn == '':
            if scope == pureldap.LDAP_SCOPE_baseObject or scope == pureldap.LDAP_SCOPE_wholeSubtree:
                results.append(self._make_entry(BASE_DN, {
                    'objectClass': [b'top', b'domain'],
                    'dc': [b'djancloud'],
                }))
            if scope in (pureldap.LDAP_SCOPE_singleLevel, pureldap.LDAP_SCOPE_wholeSubtree):
                results.append(self._make_entry(USERS_DN, {
                    'objectClass': [b'top', b'organizationalUnit'],
                    'ou': [b'Users'],
                }))
                results.append(self._make_entry(CONTACTS_DN, {
                    'objectClass': [b'top', b'organizationalUnit'],
                    'ou': [b'Contacts'],
                }))

        # Search Users OU
        if base_dn == USERS_DN.lower() or (base_dn == BASE_DN.lower() and scope == pureldap.LDAP_SCOPE_wholeSubtree):
            if scope == pureldap.LDAP_SCOPE_baseObject and base_dn == USERS_DN.lower():
                results.append(self._make_entry(USERS_DN, {
                    'objectClass': [b'top', b'organizationalUnit'],
                    'ou': [b'Users'],
                }))
            else:
                for user in User.objects.filter(is_active=True):
                    entry = self._user_to_entry(user)
                    if self._matches_filter(entry, filter_obj):
                        results.append(entry)

        # Search Contacts OU
        if base_dn == CONTACTS_DN.lower() or (base_dn == BASE_DN.lower() and scope == pureldap.LDAP_SCOPE_wholeSubtree):
            if scope == pureldap.LDAP_SCOPE_baseObject and base_dn == CONTACTS_DN.lower():
                results.append(self._make_entry(CONTACTS_DN, {
                    'objectClass': [b'top', b'organizationalUnit'],
                    'ou': [b'Contacts'],
                }))
            else:
                contacts = self._get_accessible_contacts()
                for contact in contacts:
                    entry = self._contact_to_entry(contact)
                    if self._matches_filter(entry, filter_obj):
                        results.append(entry)

        # Search specific user DN
        if base_dn.startswith('uid=') and base_dn.endswith(USERS_DN.lower()):
            uid = base_dn.split(',')[0].split('=', 1)[1]
            try:
                user = User.objects.get(username=uid, is_active=True)
                entry = self._user_to_entry(user)
                if self._matches_filter(entry, filter_obj):
                    results.append(entry)
            except User.DoesNotExist:
                pass

        # Search specific contact DN
        if base_dn.startswith('uid=') and base_dn.endswith(CONTACTS_DN.lower()):
            uid = base_dn.split(',')[0].split('=', 1)[1]
            contacts = self._get_accessible_contacts().filter(uid=uid)
            for contact in contacts:
                entry = self._contact_to_entry(contact)
                if self._matches_filter(entry, filter_obj):
                    results.append(entry)

        for entry in results:
            reply(entry)

        return pureldap.LDAPSearchResultDone(resultCode=0)

    def _get_accessible_contacts(self):
        """Return contacts accessible to the bound user."""
        from file.models import Contact, AddressBook, AddressBookShare

        if not self.bound_user:
            return Contact.objects.none()

        own_books = AddressBook.objects.filter(owner=self.bound_user).values_list('id', flat=True)
        shared_books = AddressBookShare.objects.filter(user=self.bound_user).values_list('addressbook_id', flat=True)
        all_book_ids = list(own_books) + list(shared_books)
        return Contact.objects.filter(addressbook_id__in=all_book_ids)

    def _user_to_entry(self, user):
        dn = f'uid={user.username},{USERS_DN}'
        attrs = {
            'objectClass': [b'top', b'inetOrgPerson', b'organizationalPerson', b'person'],
            'uid': [user.username.encode()],
            'cn': [(user.get_full_name() or user.username).encode()],
            'sn': [(user.last_name or user.username).encode()],
        }
        if user.first_name:
            attrs['givenName'] = [user.first_name.encode()]
        if user.email:
            attrs['mail'] = [user.email.encode()]
        return self._make_entry(dn, attrs)

    def _contact_to_entry(self, contact):
        dn = f'uid={contact.uid},{CONTACTS_DN}'
        name = (contact.fn or contact.uid or '').encode()
        attrs = {
            'objectClass': [b'top', b'inetOrgPerson', b'organizationalPerson', b'person'],
            'uid': [contact.uid.encode()],
            'cn': [name],
            'sn': [name],
        }
        if contact.fn:
            # Try to split into given/surname
            parts = contact.fn.split(' ', 1)
            attrs['givenName'] = [parts[0].encode()]
            if len(parts) > 1:
                attrs['sn'] = [parts[1].encode()]
        if contact.email:
            attrs['mail'] = [contact.email.encode()]
        if contact.tel:
            attrs['telephoneNumber'] = [contact.tel.encode()]
        if contact.org:
            attrs['o'] = [contact.org.encode()]
        return self._make_entry(dn, attrs)

    def _make_entry(self, dn, attrs):
        attr_list = []
        for name, values in attrs.items():
            attr_list.append(
                pureldap.LDAPSearchResultEntry.Attribute(
                    type=name.encode() if isinstance(name, str) else name,
                    values=values,
                )
            )
        return pureldap.LDAPSearchResultEntry(
            objectName=dn.encode() if isinstance(dn, str) else dn,
            attributes=attr_list,
        )

    def _matches_filter(self, entry, filter_obj):
        """Basic LDAP filter matching."""
        if filter_obj is None:
            return True

        if isinstance(filter_obj, pureldap.LDAPFilter_present):
            attr_name = filter_obj.value.decode().lower() if isinstance(filter_obj.value, bytes) else filter_obj.value.lower()
            for attr in entry.attributes:
                a_name = attr.type.decode().lower() if isinstance(attr.type, bytes) else attr.type.lower()
                if a_name == attr_name:
                    return True
            return False

        if isinstance(filter_obj, pureldap.LDAPFilter_equalityMatch):
            attr_name = filter_obj.attributeDesc.value.decode().lower()
            attr_val = filter_obj.assertionValue.value.lower()
            for attr in entry.attributes:
                a_name = attr.type.decode().lower() if isinstance(attr.type, bytes) else attr.type.lower()
                if a_name == attr_name:
                    for v in attr.values:
                        v_lower = v.lower() if isinstance(v, bytes) else v.encode().lower()
                        if v_lower == attr_val:
                            return True
            return False

        if isinstance(filter_obj, pureldap.LDAPFilter_substrings):
            attr_name = filter_obj.type.decode().lower()
            for attr in entry.attributes:
                a_name = attr.type.decode().lower() if isinstance(attr.type, bytes) else attr.type.lower()
                if a_name == attr_name:
                    for v in attr.values:
                        val = v.decode().lower() if isinstance(v, bytes) else v.lower()
                        if self._match_substring(val, filter_obj.substrings):
                            return True
            return False

        if isinstance(filter_obj, pureldap.LDAPFilter_and):
            return all(self._matches_filter(entry, f) for f in filter_obj)

        if isinstance(filter_obj, pureldap.LDAPFilter_or):
            return any(self._matches_filter(entry, f) for f in filter_obj)

        if isinstance(filter_obj, pureldap.LDAPFilter_not):
            return not self._matches_filter(entry, filter_obj.value)

        # Unknown filter type - pass
        return True

    def _match_substring(self, value, substrings):
        """Match LDAP substring filter."""
        pos = 0
        for sub in substrings:
            if isinstance(sub, pureldap.LDAPFilter_substrings_initial):
                s = sub.value.decode().lower() if isinstance(sub.value, bytes) else sub.value.lower()
                if not value.startswith(s):
                    return False
                pos = len(s)
            elif isinstance(sub, pureldap.LDAPFilter_substrings_any):
                s = sub.value.decode().lower() if isinstance(sub.value, bytes) else sub.value.lower()
                idx = value.find(s, pos)
                if idx < 0:
                    return False
                pos = idx + len(s)
            elif isinstance(sub, pureldap.LDAPFilter_substrings_final):
                s = sub.value.decode().lower() if isinstance(sub.value, bytes) else sub.value.lower()
                if not value.endswith(s):
                    return False
        return True

    # Reject write operations
    def handle_LDAPAddRequest(self, request, controls, reply):
        return pureldap.LDAPAddResponse(resultCode=53, errorMessage='Read-only server')

    def handle_LDAPModifyRequest(self, request, controls, reply):
        return pureldap.LDAPModifyResponse(resultCode=53, errorMessage='Read-only server')

    def handle_LDAPDelRequest(self, request, controls, reply):
        return pureldap.LDAPResult(resultCode=53, errorMessage='Read-only server')

    def handle_LDAPModifyDNRequest(self, request, controls, reply):
        return pureldap.LDAPModifyDNResponse(resultCode=53, errorMessage='Read-only server')


class LDAPServerFactory(protocol.ServerFactory):
    def buildProtocol(self, addr):
        logger.info("LDAP connection from %s", addr)
        return DjancloudLDAPServer()


class Command(BaseCommand):
    help = 'Run a read-only LDAP server exposing users and contacts'

    def add_arguments(self, parser):
        parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
        parser.add_argument('--port', type=int, default=3389, help='Port to listen on')

    def handle(self, *args, **options):
        host = options['host']
        port = options['port']

        self.stdout.write(self.style.SUCCESS(
            f'Starting LDAP server on {host}:{port}'
        ))
        self.stdout.write(f'Base DN: {BASE_DN}')
        self.stdout.write(f'Users:   {USERS_DN}')
        self.stdout.write(f'Contacts: {CONTACTS_DN}')

        endpoint = TCP4ServerEndpoint(reactor, port, interface=host)
        endpoint.listen(LDAPServerFactory())
        reactor.run()
