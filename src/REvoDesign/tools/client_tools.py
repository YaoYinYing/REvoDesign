'''
This module contains functions and classes related to generating unique identifiers (UUIDs).
'''
import uuid
from REvoDesign import issues
from REvoDesign.logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
def check_response_code(response, successfull_opt="Submitted"):
    """
    Check the HTTP response code and log information based on different status codes.
    Args:
        response (requests.Response): HTTP response object.
        successfull_opt (str): Text indicating a successful response. Defaults to 'Submitted'.
    Returns:
        None
    """
    if response.status_code == 200:
        
        logging.info(f"{successfull_opt}.\n {response.content}")
    elif response.status_code == 401:
        
        raise issues.UnauthorizedError(
            "Unauthorized.\n please retry with available username and password."
        )
    else:
        
        logging.warning(f"{response.status_code}: {response.content}")
    return
class UUIDGenerator:
    """
    This class implements a UUID generator using Python's built-in 'uuid' module.
    """
    def generate_uuid(self):
        """
        Generates a UUID using the uuid4 method.
        Returns:
        - str: A string representation of the generated UUID.
        """
        return str(uuid.uuid4())