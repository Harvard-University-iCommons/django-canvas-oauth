import logging

from django.urls import reverse
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template import loader
from django.template.exceptions import TemplateDoesNotExist
from django.utils.crypto import get_random_string

from canvas_oauth import (canvas, settings)
from canvas_oauth.models import CanvasOAuth2Token
from canvas_oauth.exceptions import (
    MissingTokenError, InvalidOAuthStateError)

logger = logging.getLogger(__name__)


def get_oauth_token(request):
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
    try:
        oauth_token = request.user.canvas_oauth2_token
        logger.info("Token found for user %s" % request.user.pk)
    except CanvasOAuth2Token.DoesNotExist:
        """ If this exception is raised by a view function and not caught,
        it is probably because the oauth_middleware is not installed, since it
        is supposed to catch this error."""
        logger.info("No token found for user %s" % request.user.pk)
        raise MissingTokenError("No token found for user %s" % request.user.pk)

    # Check to see if we're within the expiration threshold of the access token
    if oauth_token.expires_within(settings.CANVAS_OAUTH_TOKEN_EXPIRATION_BUFFER):
        logger.info("Refreshing token for user %s" % request.user.pk)
        oauth_token = refresh_oauth_token(request)

    return oauth_token.access_token


def handle_missing_token(request):
    """
    Redirect user to canvas with a request for token.
    """
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

    authorize_url = canvas.get_oauth_login_url(
        settings.CANVAS_OAUTH_CLIENT_ID,
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

    # Make the `authorization_code` grant type request to retrieve a
    access_token, expires, refresh_token = canvas.get_access_token(
        grant_type='authorization_code',
        client_id=settings.CANVAS_OAUTH_CLIENT_ID,
        client_secret=settings.CANVAS_OAUTH_CLIENT_SECRET,
        redirect_uri=request.session["canvas_oauth_redirect_uri"],
        code=code)

    obj = CanvasOAuth2Token.objects.create(
        user=request.user,
        access_token=access_token,
        expires=expires,
        refresh_token=refresh_token)
    logger.info("CanvasOAuth2Token instance created: %s" % obj.pk)

    initial_uri = request.session['canvas_oauth_initial_uri']
    logger.info("Redirecting user back to initial uri %s" % initial_uri)

    return redirect(initial_uri)


def refresh_oauth_token(request):
    """ Makes refresh_token grant request with Canvas to get a fresh
    access token.  Update the oauth token model with the new token
    and new expiration date and return the saved model.
    """
    oauth_token = request.user.canvas_oauth2_token

    # Get the new access token and expiration date via
    # a refresh token grant
    oauth_token.access_token, oauth_token.expires, _ = canvas.get_access_token(
        grant_type='refresh_token',
        client_id=settings.CANVAS_OAUTH_CLIENT_ID,
        client_secret=settings.CANVAS_OAUTH_CLIENT_SECRET,
        redirect_uri=request.build_absolute_uri(
            reverse('canvas-oauth-callback')),
        refresh_token=oauth_token.refresh_token)

    # Update the model with new token and expiration
    oauth_token.save()

    return oauth_token


def render_oauth_error(error_message):
    """ If there is an error in the oauth callback, attempts to render it in a
        template that can be styled; otherwise, if OAUTH_ERROR_TEMPLATE not
        found, this will return a HttpResponse with status 403 """
    logger.error("OAuth error %s" % error_message)
    try:
        template = loader.render_to_string(settings.CANVAS_OAUTH_ERROR_TEMPLATE,
                                           {"message": error_message})
    except TemplateDoesNotExist:
        return HttpResponse("Error: %s" % error_message, status=403)
    return HttpResponse(template, status=403)
