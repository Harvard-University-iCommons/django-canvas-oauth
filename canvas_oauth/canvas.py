import logging
from datetime import timedelta

import requests
from django.utils import timezone

from canvas_oauth.exceptions import InvalidOAuthReturnError
from canvas_oauth.settings import get_canvas_credentials

logger = logging.getLogger(__name__)

AUTHORIZE_URL_PATTERN = "https://%s/login/oauth2/auth"
ACCESS_TOKEN_URL_PATTERN = "https://%s/login/oauth2/token"


def get_oauth_login_url(domain, redirect_uri, response_type='code',
                        state=None, scopes=None, purpose=None,
                        force_login=None):
    """Builds an OAuth request url for Canvas.
    """
    client_id, _, _ = get_canvas_credentials(domain)
    authorize_url = AUTHORIZE_URL_PATTERN % domain
    scopes = " ".join(scopes) if scopes else None

    auth_request_params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': response_type,
        'state': state,
        'scope': scopes,
        'purpose': purpose,
        'force_login': force_login,
    }
    auth_request_params = sorted(auth_request_params.items(), key=lambda val: val[0])

    # Use requests library to help build our url
    auth_request = requests.Request('GET', authorize_url,
                                    params=auth_request_params)
    # Prepared request url uses urlencode for encoding and scrubs any None
    # key-value pairs
    return auth_request.prepare().url


def get_access_token(domain, grant_type, redirect_uri,
                     code=None, refresh_token=None):
    """Performs one of the two grant types supported by Canvas' OAuth endpoint to
    to retrieve an access token.  Expect a `code` kwarg when performing an
    `authorization_code` grant; otherwise, assume we're doing a `refresh_token`
    grant.

    Args:
        domain: Canvas domain (e.g., 'canvas.school.edu')
        grant_type: OAuth grant type ('authorization_code' or 'refresh_token')
        redirect_uri: OAuth redirect URI
        code: Authorization code (required for 'authorization_code' grant)
        refresh_token: Refresh token (required for 'refresh_token' grant)

    Returns:
        tuple: (access_token, expiration_datetime, refresh_token)

    Raises:
        InvalidOAuthReturnError: If the OAuth request fails
    """
    client_id, client_secret, _ = get_canvas_credentials(domain)

    # Call Canvas endpoint
    oauth_token_url = ACCESS_TOKEN_URL_PATTERN % domain
    post_params = {
        'grant_type': grant_type,  # Use 'authorization_code' for new tokens
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
    }

    # Need to add in code or refresh_token, depending on the grant_type
    if grant_type == 'authorization_code':
        post_params['code'] = code
    else:
        post_params['refresh_token'] = refresh_token

    r = requests.post(oauth_token_url, post_params)
    logger.info("%s POST response from Canvas is %s", grant_type, r.text)
    if r.status_code != 200:
        raise InvalidOAuthReturnError("%s request failed to get a token: %s" % (
            grant_type, r.text))

    # Parse the response for the access_token, expiration time, and (possibly)
    # the refresh token
    response_data = r.json()
    access_token = response_data['access_token']
    seconds_to_expire = response_data['expires_in']
    # Convert the expiration time in seconds to a DateTime
    expires = timezone.now() + timedelta(seconds=seconds_to_expire)
    # Whether a refresh token is included in the response depends on the
    # grant_type - it only appears to be returned for 'authorization_code',
    # but to be safe check the response_data for it
    refresh_token = None
    if 'refresh_token' in response_data:
        refresh_token = response_data['refresh_token']

    return (access_token, expires, refresh_token)
