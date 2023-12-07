import datetime
from absl import logging
import os
import ssl
from OpenSSL import crypto
import uuid

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
    os.makedirs(crt_dir, exist_ok=True)
    crt_path = os.path.join(crt_dir, f'{role}.crt')
    key_path = os.path.join(crt_dir, f'{role}.key')
    get_certificate(crt_path, key_path)

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


def get_certificate(crt_path, key_path):
    """
    Function: get_certificate
    Usage: get_certificate(crt_path, key_path)
    
    This function checks for the existence of an SSL certificate and generates a new one if it doesn't exist or has expired.

    Args:
    - crt_path (str): Path to the certificate file
    - key_path (str): Path to the private key file

    Returns:
    - None
    """
    # Check if the existing certificate exists
    if not os.path.exists(crt_path):
        logging.info(
            "Certificate does not exist. Generating a new certificate."
        )
        create_new_certificate(crt_path, key_path)
        return

    with open(crt_path, 'rb') as f:
        existing_cert_data = f.read()
        existing_cert = crypto.load_certificate(
            crypto.FILETYPE_PEM, existing_cert_data
        )

        # Get the expiration date of the existing certificate
        expiration_date = datetime.datetime.strptime(
            existing_cert.get_notAfter().decode('utf-8'), '%Y%m%d%H%M%SZ'
        )

    # Check if the certificate has expired
    if expiration_date < datetime.datetime.now():
        logging.warning(
            "Certificate has expired. Generating a new certificate."
        )
        create_new_certificate(crt_path, key_path)
    else:
        logging.info("Certificate is still valid.")


def create_new_certificate(crt_path, key_path):
    """
    Function: create_new_certificate
    Usage: create_new_certificate(crt_path, key_path)
    
    This function creates a new SSL certificate and private key if they do not exist or if the certificate has expired.

    Args:
    - crt_path (str): Path to the certificate file
    - key_path (str): Path to the private key file

    Returns:
    - None
    """
    # Extract role from the certificate path
    role = os.path.basename(crt_path).replace('.crt', '')

    # Get node information from OS or set to 'Unknown' if not available
    from REvoDesign.tools.system_tools import OS_INFO

    node = OS_INFO.node if OS_INFO.node else 'Unknown'

    # Generate RSA key
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)

    # Create an X.509 certificate
    cert = crypto.X509()
    # Set subject information
    cert.get_subject().C = "CN"
    cert.get_subject().ST = "Yunnan"
    cert.get_subject().L = "Kunming"
    cert.get_subject().O = "JAPS"
    cert.get_subject().OU = "Yunnan Abnormal University"
    cert.get_subject().CN = f"{node}.{role}.REvoDesign"

    # Set serial number, validity period, issuer, public key, and sign the certificate
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(7 * 24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')

    # Write the certificate and private key to files in PEM format
    with open(crt_path, 'wb') as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    with open(key_path, 'wb') as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))



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