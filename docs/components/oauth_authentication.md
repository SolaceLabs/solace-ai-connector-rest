# OauthAuthentication

OAuth authentication component that handles user authentication through various OAuth providers. Currently supports Google and Azure OAuth providers. Provides endpoints for login, callback handling, token refresh, user info retrieval and token validation.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: oauth_authentication
component_config:
  oauth_authentication:
    provider: <string>           # OAuth provider ("google" or "azure")
    client_id: <string>         # OAuth client ID
    client_secret: <string>     # OAuth client secret
    https_cert: <string>        # Path to HTTPS certificate (optional)
    https_key: <string>         # Path to HTTPS private key (optional) 
    tenant_id: <string>         # Azure tenant ID (required for Azure)
    enabled: <boolean>          # Enable/disable authentication
  listen_port: <number>         # Port to listen on (default: 8000)
  host: <string>               # Host to bind to (default: 127.0.0.1)
```

## Endpoints

### /login (GET)
Initiates the OAuth login flow by redirecting to the provider's authorization URL.

### /callback (GET) 
Handles the OAuth callback after successful authorization. Exchanges the authorization code for access tokens.

### /refresh_token (POST)
Refreshes an expired access token using a refresh token.

Request body:
```json
{
    "refresh_token": "your-refresh-token"
}
```

### /user_info (GET)
Retrieves user information from the OAuth provider.

Response example:
```json
{
    "email": "user@example.com",
    "user_id": "12345"
}
```

### /is_token_valid (POST)
Validates an access token with the OAuth provider.

Response indicates if the token is valid or has expired.

## Security

- Uses HTTPS when configured with certificate and private key
- Implements CSRF protection using state parameter
- Supports token refresh for expired access tokens
- Validates tokens with provider before granting access
