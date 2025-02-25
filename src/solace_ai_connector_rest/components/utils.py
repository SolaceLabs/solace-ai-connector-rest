import requests
from flask import jsonify
from solace_ai_connector.common.log import log


def create_api_response(data, status_code=200) -> tuple:
    """
    Create an API response with the given data and status code.

    Args:
        data (dict): The data to include in the response.
        status_code (int): The HTTP status code for the response.

    Returns:
        Response: A Flask response object with the given data and status code.
    """
    response = jsonify(data), status_code
    return response


def get_user_info(server_address, token_id):
    """
    Get user info from the authentication server.

    Args:
        server_address (str): The address of the authentication server.
        token_id (str): The bearer token.

    Returns:
        dict: The user info.
    """
    try:
        response = requests.post(
            f"{server_address}/is_token_valid",
            headers={
                "Authorization": f"Bearer {token_id}",
                "Content-Type": "application/json",
            },
            timeout=10,
            verify=False,
        )
        if response.status_code != 200:
            return response.json(), response.status_code
        else:
            response = requests.get(
                f"{server_address}/user_info",
                headers={"Authorization": f"Bearer {token_id}"},
                timeout=10,
                verify=False,
            )

            if response.status_code == 200:
                return response.json(), response.status_code
            else:
                return "Could not find the user", response.status_code
    except requests.exceptions.RequestException as e:
        log.error("Error getting user info: %s", e)
        return f"Error getting user info: {e}", 500
