from .schemas import SUPPORTED_VULNERABILITY_TYPES
from .specialists import (
    AuthBypassSpecialistAgent,
    CommandInjectionSpecialistAgent,
    GenericSecuritySpecialistAgent,
    PathTraversalSpecialistAgent,
    SQLiSpecialistAgent,
    XSSSpecialistAgent,
)


class SpecialistRegistry:
    def __init__(self, mapping=None):
        self.mapping = {
            'SQL_INJECTION': SQLiSpecialistAgent,
            'XSS': XSSSpecialistAgent,
            'AUTH_BYPASS': AuthBypassSpecialistAgent,
            'PATH_TRAVERSAL': PathTraversalSpecialistAgent,
            'COMMAND_INJECTION': CommandInjectionSpecialistAgent,
            'SSRF': GenericSecuritySpecialistAgent,
            'DESERIALIZATION': GenericSecuritySpecialistAgent,
            'SECRETS': GenericSecuritySpecialistAgent,
            'ACCESS_CONTROL': GenericSecuritySpecialistAgent,
            'FILE_UPLOAD': GenericSecuritySpecialistAgent,
            'TEMPLATE_INJECTION': GenericSecuritySpecialistAgent,
            'OTHER': GenericSecuritySpecialistAgent,
        }
        if mapping:
            self.mapping.update(mapping)

    def get_specialist_class(self, vulnerability_type):
        normalized = (vulnerability_type or 'OTHER').upper()
        if normalized not in SUPPORTED_VULNERABILITY_TYPES:
            return GenericSecuritySpecialistAgent
        return self.mapping.get(normalized, GenericSecuritySpecialistAgent)

    def create(self, vulnerability_type, *args, **kwargs):
        return self.get_specialist_class(vulnerability_type)(*args, **kwargs)
