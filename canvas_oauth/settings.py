# -*- coding: utf-8 -*-
"""
canvas_oauth specific settings
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from canvas_oauth import settings as oauth_settings


def get_required_setting(setting_name):
    """
    Check for and return required OAuth setting here so we can
    raise an error if not found.
    """
    try:
        return getattr(settings, setting_name)
    except AttributeError:
        raise ImproperlyConfigured(f"{setting_name} setting is required")


def get_environment_resolver():
    """Get the configured environment resolver"""
    resolver_path = getattr(settings, 'CANVAS_OAUTH_ENVIRONMENT_RESOLVER',
                           'canvas_oauth.resolvers.SingleEnvironmentResolver')

    module_path, class_name = resolver_path.rsplit('.', 1)
    module = __import__(module_path, fromlist=[class_name])
    resolver_class = getattr(module, class_name)

    return resolver_class()


def get_canvas_credentials(domain):
    """
    Get Canvas OAuth credentials for a specific domain.
    """
    # Check for multi-environment config
    environments_config = getattr(settings, 'CANVAS_OAUTH_ENVIRONMENTS', {})
    for env_key, env_config in environments_config.items():
        if env_config.get('domain') == domain:
            client_id = env_config.get('client_id')
            client_secret = env_config.get('client_secret')
            if client_id and client_secret:
                return client_id, client_secret, f"https://{domain}"

    client_id = oauth_settings.get_client_id_for_domain(domain)
    client_secret = oauth_settings.get_client_secret_for_domain(domain)

    if not client_id or not client_secret:
        raise ImproperlyConfigured(
            f"Canvas OAuth credentials not found for domain: {domain}. "
            f"Please configure CANVAS_OAUTH_ENVIRONMENTS or domain-specific settings."
        )

    return client_id, client_secret, f"https://{domain}"


# Single environment support - check if new multi-environment config exists
if hasattr(settings, 'CANVAS_OAUTH_ENVIRONMENTS') and settings.CANVAS_OAUTH_ENVIRONMENTS:
    pass
else:
    CANVAS_OAUTH_CLIENT_ID = get_required_setting('CANVAS_OAUTH_CLIENT_ID')
    CANVAS_OAUTH_CLIENT_SECRET = get_required_setting('CANVAS_OAUTH_CLIENT_SECRET')
    CANVAS_OAUTH_CANVAS_DOMAIN = get_required_setting('CANVAS_OAUTH_CANVAS_DOMAIN')


# Optional settings
# -----------------

# Buffer for refreshing a token when retrieving via `get_token`, expressed
# as a timedelta. Tokens are refreshed this amount of time before they expire.
# Canvas tokens expire after 1 hour, so setting this to timedelta(minutes=5)
# means tokens refresh at the 55-minute mark.
CANVAS_OAUTH_TOKEN_EXPIRATION_BUFFER = getattr(
    settings,
    'CANVAS_OAUTH_TOKEN_EXPIRATION_BUFFER',
    timedelta(),
)

CANVAS_OAUTH_ERROR_TEMPLATE = getattr(
    settings,
    'CANVAS_OAUTH_ERROR_TEMPLATE',
    'oauth_error.html'
)


# Environment-specific credential helpers
# =======================================

def get_client_id_for_domain(domain):
    """Get client ID for a specific Canvas domain from settings"""
    # Check for domain-specific setting first
    domain_setting = f'CANVAS_OAUTH_{domain.upper().replace(".", "_")}_CLIENT_ID'
    domain_client_id = getattr(settings, domain_setting, None)
    if domain_client_id:
        return domain_client_id

    # Fall back to main setting
    return getattr(settings, 'CANVAS_OAUTH_CLIENT_ID', '')


def get_client_secret_for_domain(domain):
    """Get client secret for a specific Canvas domain from settings"""
    # Check for domain-specific setting first
    domain_setting = f'CANVAS_OAUTH_{domain.upper().replace(".", "_")}_CLIENT_SECRET'
    domain_client_secret = getattr(settings, domain_setting, None)
    if domain_client_secret:
        return domain_client_secret

    # Fall back to main setting
    return getattr(settings, 'CANVAS_OAUTH_CLIENT_SECRET', '')

# A list of Canvas API scopes that the access token will provide access to.
#
# This is only required if the Canvas API developer key requires scopes
# (e.g. enforces scopes). Otherwise, the access token will have access to
# all scopes.
#
# Note that Canvas API scopes may be found beneath their corresponding
# endpoints in the "resources" documentation pages.
CANVAS_OAUTH_SCOPES = getattr(
    settings,
    'CANVAS_OAUTH_SCOPES',
    []
)
