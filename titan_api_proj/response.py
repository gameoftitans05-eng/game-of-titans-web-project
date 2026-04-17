from rest_framework.response import Response
from rest_framework import status

class APIResponse(Response):
    def __init__(self, success=True, message='', data=None, status_code=None, **kwargs):
        # Default data to an empty dict if None
        data = data or {}
        # Construct the standardized response
        response_data = {
            'success': success,
            'message': message,
            'data': data
        }
        # Use provided status_code or default based on success
        status_code = status_code or (status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)
        super().__init__(data=response_data, status=status_code, **kwargs)
        