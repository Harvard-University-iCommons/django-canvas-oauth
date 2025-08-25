import logging

from django.core.exceptions import ImproperlyConfigured
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template import loader
from django.template.exceptions import TemplateDoesNotExist
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string

from canvas_oauth import settings
from canvas_oauth.canvas import get_access_token, get_oauth_login_url
from canvas_oauth.exceptions import InvalidOAuthStateError, MissingTokenError
from canvas_oauth.models import CanvasOAuth2Token

logger = logging.getLogger(__name__)


def get_oauth_token(request, domain=None):
    """Retrieve a stored Canvas OAuth2 access token from Canvas for the
    currently logged in user.  If the token has expired (or has exceeded an
    expiration threshold as defined by the consuming project), a fresh token
    is generated via the saved refresh token.

    If the user does not have a stored token, the method raises a
    MissingTokenError exception.  If this happens inside a view, this exception
    will be handled by the middleware component of this library with a call to
    handle_missing_token.  If this happens outside of a view, then the user must
    be directed by other means to the Canvas site in order to authorize a token.
    """
    if not domain:
        resolver = settings.get_environment_resolver()
        domain = resolver.resolve_domain(request)

        if not domain:
            raise MissingTokenError("Cannot resolve Canvas domain")

    try:
        oauth_token = CanvasOAuth2Token.objects.get(
            user=request.user,
            canvas_domain=domain
        )
        logger.info(f"Token found for user {request.user.pk} in domain {domain}")
    except CanvasOAuth2Token.DoesNotExist:
        """ If this exception is raised by a view function and not caught,
        it is probably because the oauth_middleware is not installed, since it
        is supposed to catch this error."""
        logger.info(f"No token found for user {request.user.pk} in domain {domain}")
        raise MissingTokenError(f"No token found for user {request.user.pk} in domain {domain}")

    # Check to see if we're within the expiration threshold of the access token
    # Use the same buffer logic as the original system, just domain-aware
    if oauth_token.expires_within(settings.CANVAS_OAUTH_TOKEN_EXPIRATION_BUFFER):
        logger.info(f"Refreshing token for user {request.user.pk} in domain {domain}")
        oauth_token = refresh_oauth_token(request, domain)

    return oauth_token.access_token


def handle_missing_token(request, domain=None):
    """
    Redirect user to canvas with a request for token.
    """
    if not domain:
        resolver = settings.get_environment_resolver()
        domain = resolver.resolve_domain(request)

        if not domain:
            raise ImproperlyConfigured("Cannot resolve Canvas domain for OAuth")

    # Store domain in session for OAuth callback
    request.session['oauth_canvas_domain'] = domain

    # Store where the user came from so they can be redirected back there
    # at the end.  https://canvas.instructure.com/doc/api/file.oauth.html
    request.session["canvas_oauth_initial_uri"] = request.get_full_path()

    # The request state is a recommended security check on the callback, so
    # store in session for later
    oauth_request_state = get_random_string(12)
    request.session["canvas_oauth_request_state"] = oauth_request_state

    # The return URI is required to be the same when POSTing to generate
    # a token on callback, so also store it in session (although it could
    # be regenerated again via the same method call).
    oauth_redirect_uri = request.build_absolute_uri(reverse('canvas-oauth-callback'))
    request.session["canvas_oauth_redirect_uri"] = oauth_redirect_uri

    authorize_url = get_oauth_login_url(
        domain,
        redirect_uri=oauth_redirect_uri,
        state=oauth_request_state,
        scopes=settings.CANVAS_OAUTH_SCOPES)

    logger.info("Redirecting user to %s" % authorize_url)
    return HttpResponseRedirect(authorize_url)


def oauth_callback(request):
    """ Receives the callback from canvas and saves the token to the database.
        Redirects user to the page they came from at the start of the oauth
        procedure. """
    error = request.GET.get('error')
    if error:
        return render_oauth_error(error)
    code = request.GET.get('code')
    state = request.GET.get('state')

    if state != request.session['canvas_oauth_request_state']:
        logger.warning("OAuth state mismatch for request: %s" % request.get_full_path())
        raise InvalidOAuthStateError("OAuth state mismatch!")

    # Get domain from session
    domain = request.session.get('oauth_canvas_domain')
    if not domain:
        return render_oauth_error("Missing domain information")

    # Make the `authorization_code` grant type request to retrieve a token
    access_token, expires, refresh_token = get_access_token(
        domain=domain,
        grant_type='authorization_code',
        redirect_uri=request.session["canvas_oauth_redirect_uri"],
        code=code)

    obj, created = CanvasOAuth2Token.objects.update_or_create(
        user=request.user,
        canvas_domain=domain,
        defaults={
            'access_token': access_token,
            'expires': expires,
            'refresh_token': refresh_token or ''
        }
    )
    logger.info("CanvasOAuth2Token instance %s: %s" % ('created' if created else 'updated', obj.pk))

    # Clean up session
    request.session.pop('oauth_canvas_domain', None)
    request.session.pop('canvas_oauth_request_state', None)
    request.session.pop('canvas_oauth_redirect_uri', None)

    # Redirect the user back to where they started
    uri = request.session.pop("canvas_oauth_initial_uri", "/")
    return HttpResponseRedirect(uri)


def refresh_oauth_token(request, domain=None):
    """
    Use refresh token to generate a new access token.

    If refresh fails, clears the user's token and raises MissingTokenError,
    which should cause a redirect to authorize a new token.
    """
    if not domain:
        resolver = settings.get_environment_resolver()
        domain = resolver.resolve_domain(request)

        if not domain:
            raise MissingTokenError("Cannot resolve Canvas domain")

    try:
        oauth_token = CanvasOAuth2Token.objects.get(
            user=request.user,
            canvas_domain=domain
        )
    except CanvasOAuth2Token.DoesNotExist:
        logger.info(f"No token found for user {request.user.pk} in domain {domain}")
        raise MissingTokenError(f"No token found for user {request.user.pk} in domain {domain}")

    logger.info("Refreshing token for user %s in domain %s" % (request.user.pk, domain))

    try:
        access_token, expires, refresh_token = get_access_token(
            domain=domain,
            grant_type='refresh_token',
            redirect_uri='',
            refresh_token=oauth_token.refresh_token)

        oauth_token.access_token = access_token
        oauth_token.expires = expires
        if refresh_token:
            oauth_token.refresh_token = refresh_token
        oauth_token.save()

        return oauth_token

    except Exception:
        # Delete the token on refresh failure so user gets sent through
        # authorization flow again
        logger.exception("Token refresh failed for user %s in domain %s, deleting token"
                        % (request.user.pk, domain))
        oauth_token.delete()
        raise MissingTokenError(f"Token refresh failed for user {request.user.pk} in domain {domain}")


def render_oauth_error(error):
    """
    Render an OAuth error template.
    """
    try:
        template = loader.get_template(settings.CANVAS_OAUTH_ERROR_TEMPLATE)
        return HttpResponse(template.render({'error': error}))
    except TemplateDoesNotExist:
        return HttpResponse(f"OAuth Error: {error}")
