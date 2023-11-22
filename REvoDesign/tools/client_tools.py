from absl import logging

def check_response_code(response,successfull_opt='Submitted'):
    if response.status_code == 200:
        logging.info(f"{successfull_opt}.\n {response.content}")
    elif response.status_code == 401:
        logging.warning(f"Unauthorized.\n please retry with available username and password.")
    else:
        logging.warning(f"{response.status_code}: {response.content}")
    return