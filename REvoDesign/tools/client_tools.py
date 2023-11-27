from absl import logging
import os
import ssl
from OpenSSL import crypto


def check_response_code(response, successfull_opt='Submitted'):
    """
    Check the HTTP response code and log information based on different status codes.

    Args:
        response (requests.Response): HTTP response object.
        successfull_opt (str): Text indicating a successful response. Defaults to 'Submitted'.

    Returns:
        None
    """
    if response.status_code == 200:
        # Log successful response with content if status code is 200
        logging.info(f"{successfull_opt}.\n {response.content}")
    elif response.status_code == 401:
        # Log a warning for unauthorized access if status code is 401
        logging.warning(
            f"Unauthorized.\n please retry with available username and password."
        )
    else:
        # Log a warning with status code and content for other status codes
        logging.warning(f"{response.status_code}: {response.content}")
    return


def generate_ssl_context(role='server'):
    """
    Generate an SSL context based on the specified role for server or client.

    Args:
    role (str): Role for which the SSL context is generated ('server' or 'client').

    Returns:
    ssl.SSLContext: Generated SSL context.

    Raises:
    ValueError: If an unknown role is provided.
    FileNotFoundError: If client certificate is not found.
    """
    # Generate SSL context and certificate if needed
    crt_dir = os.path.expanduser('~/.REvoDesign/crts/')
    os.makedirs(crt_path, exist_ok=True)
    crt_path = os.path.join(crt_dir, 'server.crt')
    key_path = os.path.join(crt_dir, 'server.key')

    if not os.path.exists(crt_path) or not os.path.exists(key_path):
        create_certificate(crt_path, key_path)

    if role == 'server':
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(crt_path, key_path)
    elif role == 'client':
        context = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH, cafile=crt_path
        )
    else:
        raise ValueError(f'Unknown role of ssl context: {role}')
    return context


def create_certificate(crt_path, key_path):
    if not os.path.exists(os.path.dirname(crt_path)):
        os.makedirs(os.path.dirname(crt_path))

    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)
    cert = crypto.X509()
    cert.get_subject().C = "Country"
    cert.get_subject().ST = "State"
    cert.get_subject().L = "Location"
    cert.get_subject().O = "Organization"
    cert.get_subject().OU = "Organizational Unit"
    cert.get_subject().CN = "Common Name"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')

    with open(crt_path, 'wb') as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    with open(key_path, 'wb') as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
