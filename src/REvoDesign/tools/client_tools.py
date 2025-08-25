import uuid
from REvoDesign import issues
from REvoDesign.logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
def check_response_code(response, successfull_opt="Submitted"):
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
    def generate_uuid(self):
        return str(uuid.uuid4())