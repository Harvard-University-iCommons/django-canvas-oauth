import logging
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

class EnvironmentResolver(ABC):
    """Abstract base class for Canvas environment resolution"""

    @abstractmethod
    def resolve_domain(self, request, **kwargs):
        """
        Resolve Canvas domain from request context
        Returns: domain string or None
        """
        pass


class LtiBasedResolver(EnvironmentResolver):
    """
    Resolves Canvas domain for LTI tools.

    This resolver supports multiple methods to extract the Canvas domain:
      - Direct from LTI custom fields (api_domain=$Canvas.api.domain)
      - From request session storage
      - From Canvas URLs in LTI claims (fallback)
    """

    def resolve_domain(self, request, **kwargs):
        # Always check LTI data first if available to ensure fresh launches use correct domain
        lti_data = kwargs.get('lti_data')
        if lti_data:
            canvas_domain = self.extract_domain_from_lti_data(lti_data)
            if canvas_domain:
                # Update both session and request cache with fresh domain
                request.session['canvas_domain'] = canvas_domain
                request._canvas_domain = canvas_domain
                return canvas_domain

        # Fall back to cached values only if no LTI data is available
        canvas_domain = getattr(request, '_canvas_domain', None)
        if not canvas_domain:
            canvas_domain = request.session.get('canvas_domain')

        if canvas_domain:
            return canvas_domain

        return None

    def extract_domain_from_lti_data(self, lti_data):
        """
        Extract Canvas domain from LTI launch data.

        Priority order:
        1. Direct from api_domain custom field
        2. Parse from Canvas URLs in LTI claims
        """
        # Check for api_domain custom field
        # This is set via developer key custom fields: api_domain=$Canvas.api.domain
        custom_fields = lti_data.get('https://purl.imsglobal.org/spec/lti/claim/custom', {})
        api_domain = custom_fields.get('api_domain')

        if api_domain:
            return api_domain

        # Fallback - parse from Canvas URLs in LTI claims
        return self._extract_domain_from_lti_urls(lti_data)

    def _extract_domain_from_lti_urls(self, lti_data):
        """Fallback method - extract domain from Canvas URLs in LTI claims"""
        ags_claim = lti_data.get('https://purl.imsglobal.org/spec/lti-ags/claim/endpoint', {})
        if ags_claim and 'lineitems' in ags_claim:
            domain = self.extract_domain_from_url(ags_claim['lineitems'])
            if domain:
                return domain

        nrps_claim = lti_data.get('https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice', {})
        if nrps_claim and 'context_memberships_url' in nrps_claim:
            domain = self.extract_domain_from_url(nrps_claim['context_memberships_url'])
            if domain:
                return domain

        launch_presentation = lti_data.get('https://purl.imsglobal.org/spec/lti/claim/launch_presentation', {})
        if launch_presentation and 'return_url' in launch_presentation:
            domain = self.extract_domain_from_url(launch_presentation['return_url'])
            if domain:
                return domain

        return None

    def extract_domain_from_url(self, url):
        """Extract domain from Canvas URL - utility method"""
        if not url:
            return None

        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            # Remove 'www.' prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return None


class SingleEnvironmentResolver(EnvironmentResolver):
    """
    Resolver for single-environment setups.

    This resolver requires CANVAS_OAUTH_CANVAS_DOMAIN to be configured
    """

    def resolve_domain(self, request, **kwargs):
        if not hasattr(settings, 'CANVAS_OAUTH_CANVAS_DOMAIN'):
            logger.warning("SingleEnvironmentResolver requires CANVAS_OAUTH_CANVAS_DOMAIN setting")
            return None

        domain = getattr(settings, 'CANVAS_OAUTH_CANVAS_DOMAIN')
        if not domain:
            logger.warning("CANVAS_OAUTH_CANVAS_DOMAIN setting is empty")
            return None

        return domain
