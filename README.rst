.. figure:: ./coverage.svg
   :alt: Coverage Status

============
Django Canvas OAuth
============

**Django Canvas OAuth** is a Django app that manages OAuth2 Tokens used to make API calls against a Canvas LMS instance.

The `OAuth workflow`_ is managed by this library and a CanvasOAuth2Token model is used to store authenticated tokens for each Canvas domain. Users can have multiple tokens (one per Canvas domain) to support multi-environment setups.
Tokens are short-lived, so some logic is introduced at the point of retrieving the the stored token to capture and handle the necessary refresh calls.

.. _OAuth workflow: https://canvas.instructure.com/doc/api/file.oauth.html

Installation
------------

Requires python >= 3.6 and Django >= 2.0

.. code-block:: bash

    pip install git+https://github.com/Harvard-University-iCommons/django-canvas-oauth.git#egg=canvas-oauth


Quickstart
----------

1. Add "canvas_oauth" to your INSTALLED_APPS setting like this::

.. code-block:: python

    INSTALLED_APPS = [
        # ...
        'canvas_oauth.apps.CanvasOAuthConfig',
    ]

2. Include the canvas_oauth URLconf in your project urls.py like this::

.. code-block:: python

    path('oauth/', include('canvas_oauth.urls')),

3. Install middleware to begin the oauth2 dance when a token is not
   present and to consume any errors encountered by the library.

.. code-block:: python

    MIDDLEWARE = [
        # ...
        'canvas_oauth.middleware.OAuthMiddleware',
    ]

4. Run ``python manage.py migrate`` to create the canvas_oauth models.

5. Use the ``get_oauth_token`` method from ``canvas_oauth.oauth`` to obtain a
   token. This method contains all of the logic to obtain a new token, refresh
   an expired one, or return an existing one.

.. code-block:: python

    from canvas_oauth.oauth import get_oauth_token

    access_token = get_oauth_token(request)
    #  Make request to the Canvas API using above token.


Settings
---------

Settings should be added to your django settings module (e.g. ``settings.py``).

Single-Environment Settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For simple setups with a single Canvas instance, use these settings:

CANVAS_OAUTH_CLIENT_ID:
    (required for single-environment) The client id is the integer client id value of your Canvas developer key.

CANVAS_OAUTH_CLIENT_SECRET:
    (required for single-environment) The client secret is the random string (secret) value of your Canvas developer key.

CANVAS_OAUTH_CANVAS_DOMAIN:
    (required for single-environment) The domain of your canvas instance (e.g. canvas.instructure.com)

Multi-Environment Settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~

For LTI tools working with multiple Canvas instances, use these settings instead:

CANVAS_OAUTH_ENVIRONMENTS:
    (required for multi-environment) Dictionary defining multiple Canvas instances with their OAuth credentials and domains. See Multi-Environment Support section for details.

CANVAS_OAUTH_ENVIRONMENT_RESOLVER:
    (required for multi-environment) Class path for environment resolution strategy. Use ``'canvas_oauth.resolvers.LtiBasedResolver'`` for automatic LTI-based detection.

Common Settings
~~~~~~~~~~~~~~~

These settings apply to both single and multi-environment configurations:

CANVAS_OAUTH_SCOPES:
    (optional) Specify a list of Canvas API scopes that the access token will provide access to. Canvas API scopes may be found beneath their corresponding endpoints in the "resources" documentation pages. If the developer key does not require scopes and no scopes are specified, the access token will have access to all scopes. Defaults to ``[]``.

CANVAS_OAUTH_TOKEN_EXPIRATION_BUFFER:
    (optional) Specify a ``datetime.timedelta`` that will force a refresh of the access token before it expires according to the ``expires_in`` parameter included in the access token response. Defaults to ``timedelta(0)``.

CANVAS_OAUTH_ERROR_TEMPLATE:
    (optional) Specify a template for rendering errors that occur in the authorization flow. Defaults to ``oauth_error.html``.


Multi-Environment Support
--------------------------

For LTI tools that need to work with multiple Canvas instances (e.g., production and test environments), django-canvas-oauth supports automatic environment detection.

Setup
~~~~~

1. **Configure environments in settings:**

.. code-block:: python

    # Multi-environment configuration
    CANVAS_OAUTH_ENVIRONMENTS = {
        'production': {
            'client_id': 'your_prod_client_id',
            'client_secret': 'your_prod_secret',
            'canvas_domain': 'canvas.school.edu',
            'name': 'School Canvas',
        },
        'test': {
            'client_id': 'your_test_client_id',
            'client_secret': 'your_test_secret',
            'canvas_domain': 'canvas.test.school.edu',
            'name': 'School Canvas (Test)',
        },
    }

    # Enable domain-based environment detection
    CANVAS_OAUTH_ENVIRONMENT_RESOLVER = 'canvas_oauth.resolvers.LtiBasedResolver'

2. **Run migrations:**

.. code-block:: bash

    python manage.py migrate canvas_oauth

3. **Add Canvas custom field:**

Add this custom field to your LTI Developer Key configuration:

.. code-block::

    api_domain=$Canvas.api.domain

Multi-Environment Usage
~~~~~~~~~~~~~~~~~~~~~~~~

Example Django view application code for an LTI tool:

.. code-block:: python
    from canvas_oauth.oauth import get_oauth_token
    from canvas_oauth.settings import get_environment_resolver
    import requests

    def get_user_courses(request):
        # Get OAuth token for the current Canvas domain
        # This automatically selects the correct token for the domain
        access_token = get_oauth_token(request)

        # Store LTI data for subsequent use
        # In this example, get_lti_data() is a dummy function
        lti_data = get_lti_data()

        # Determine the Canvas domain for the API base URL
        resolver = oauth_settings.get_environment_resolver()
        domain = resolver.resolve_domain(request, lti_data=lti_data)

        # Construct API URL
        api_url = f"https://{canvas_domain}/api/v1/courses"

        # Make API call
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        response = requests.get(api_url, headers=headers)

Single Environment Usage
------

Wherever you are making API requests in your code, use the ``get_oauth_token`` method to retrieve a token.

Example:

.. code-block:: python

    from canvas_oauth.oauth import get_oauth_token

    @login_required
    def index(request):
        access_token = get_oauth_token(request)
        #  Make request to the Canvas API using above token.

**Implementation notes:**

- The ``get_oauth_token`` assumes that ``request.user`` is authenticated.
- The ``get_oauth_token`` method will raise an ``MissingTokenError`` exception if no token is present (e.g. new user). The exception is handled by the middleware, which then initiates the Oauth2 flow. The user will be returned to the original view once the authorization completes successfully.
- The ``get_oauth_token`` method automatically refreshes expired tokens. By default, the token is not refreshed until it has fully expired. However, you can force the token to refresh earlier by configuring an expiration buffer period (defined as a timedelta by the consuming project).

**Best practices:**

- Avoid storing the access token in a session to use across views. If you do so, your application will be responsible for handling invalid token errors that may arise when the token expires.


Development
-----------

Setup environment:

.. code-block:: bash

    $ python3 -m venv ~/.virtualenvs/django-canvas-oauth
    $ source ~/.virtualenvs/django-canvas-oauth/bin/activate
    $ pip install -r requirements-dev.txt

To run tests in your venv:

.. code-block:: bash

    $ python run_tests.py

Or to run tests against multiple versions of python and django use tox_:

.. code-block:: bash

    $ tox
    $ tox -e flake8

.. _tox: https://tox.readthedocs.io/

To update the coverage badge:

.. code-block:: bash

    $ coverage run --source='.' run_tests.py
    $ coverage-badge -f -o coverage.svg
