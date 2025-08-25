# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Multi-environment Canvas OAuth support for LTI tools
- Automatic Canvas domain detection from LTI launch data
- New `canvas_domain` field to map user tokens to canvas domains
- New `LtiBasedResolver` for automatic environment detection from LTI launches
- New `SingleEnvironmentResolver` for backward compatibility with single-environment setups
- Enhanced resolver with automatic LTI domain extraction

### Changed

- `CanvasOAuth2Token.user` field changed from `OneToOneField` to `ForeignKey` to support multiple tokens per user (one per environment)
- Added `unique_together` constraint on `CanvasOAuth2Token` for `(user, canvas_domain)` pairs

### Migration Guide

#### For Existing Installations

1. Run migrations to upgrade database schema:

   ```bash
   python manage.py migrate canvas_oauth
   ```

2. **No code changes required** - existing single-environment setups continue to work unchanged

#### For Multi-Environment Setup

1. Configure multiple environments in settings:

   ```python
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
   CANVAS_OAUTH_ENVIRONMENT_RESOLVER = 'canvas_oauth.resolvers.LtiBasedResolver'
   ```

2. Add Canvas custom field to your LTI Developer Key:

   ```text
   api_domain=$Canvas.api.domain
   ```

3. Example Django view application code for an LTI tool:

    ```python
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
    ```

### New Settings

- `CANVAS_OAUTH_ENVIRONMENTS` - Dictionary defining multiple Canvas instances with their OAuth credentials
- `CANVAS_OAUTH_ENVIRONMENT_RESOLVER` - Class path for environment resolution strategy

### Technical Details

- Migration `0003_canvasoauth2token_canvas_domain_and_more` - Adds `canvas_domain`
field and migrates existing tokens to populate that field with the value defined in `CANVAS_OAUTH_CANVAS_DOMAIN` (if present)
