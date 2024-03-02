import os
import hashlib
from typing import Union
import requests
from REvoDesign.REvoDesign import logging as logger

from requests.auth import HTTPBasicAuth

logging = logger.getChild(__name__)

from REvoDesign.tools.client_tools import check_response_code


class PSSMGremlinCalculator:
    def __init__(self):
        self.url = ''
        self.user = ''
        self.password = ''
        self.auth: Union[HTTPBasicAuth, None] = None
        pass

    def setup_calculator(
        self, working_directory, molecule, chain_id, sequence
    ):
        self.WORKING_DIR = working_directory
        self.DOWNLOAD_DIR = os.path.join(self.WORKING_DIR, 'downloaded')
        os.makedirs(self.DOWNLOAD_DIR, exist_ok=True)

        # Create a temporary FASTA file
        temp_file_name = f"{molecule}_{chain_id}.fasta"
        self.temp_file_path = os.path.join(self.WORKING_DIR, temp_file_name)
        with open(self.temp_file_path, 'w') as fasta_file:
            fasta_file.write(f'>{molecule}_{chain_id}\n{sequence}\n')

        logging.info(f"Saved sequence file: {self.temp_file_path}")

        # Calculate MD5 sum of the FASTA file
        self.md5sum = self.calculate_md5sum(self.temp_file_path)

        logging.info(f'Calculated MD5 sum {self.md5sum}')

    def submit_remote_pssm_gremlin_calc(self, opt):
        if opt == 'submit':
            # Submit the file by posting the FASTA file
            response = self.submit_fasta_file(self.temp_file_path)
            check_response_code(response, successfull_opt='Submitted')
            return

        elif opt == 'cancel':
            # Cancel the job by posting the cancel URL
            response = self.cancel_job(self.md5sum)
            check_response_code(response=response, successfull_opt='Cancelled')
            return

        elif opt == 'download':
            # Directly attempt to download the results
            self.download_results(self.md5sum)

        else:
            logging.warning(f"Unknown option: {opt}")

    def calculate_md5sum(self, file_path):
        md5sum = hashlib.md5()
        with open(file_path, 'rb') as file:
            for chunk in iter(lambda: file.read(4096), b''):
                md5sum.update(chunk)
        return md5sum.hexdigest()

    def submit_fasta_file(self, fasta_file_path):
        files = {
            'file': (
                os.path.basename(fasta_file_path),
                open(fasta_file_path, 'rb'),
            )
        }
        response = requests.post(
            f'{self.url}/PSSM_GREMLIN/api/post',
            files=files,
            timeout=10,
            auth=self.auth,
        )
        return response

    def cancel_job(self, md5sum):
        response = requests.post(
            f'{self.url}/PSSM_GREMLIN/api/cancel/{md5sum}',
            timeout=10,
            auth=self.auth,
        )
        return response

    def download_results(self, md5sum):
        result_url = f'{self.url}/PSSM_GREMLIN/api/results/{md5sum}'
        response = requests.get(
            result_url,
            stream=True,
            allow_redirects=False,
            auth=self.auth,
        )

        if response.status_code == 302:  # Redirection status code
            redirected_url = response.headers['Location']
            logging.info(f"Redirected to download page: {redirected_url}")
            self.download_from_redirected_url(redirected_url, md5sum)
        else:
            check_response_code(response=response, successfull_opt="")

    def download_from_redirected_url(self, redirected_url, md5sum):
        response = requests.get(
            f'{self.url}/{redirected_url}',
            stream=True,
            auth=self.auth,
        )

        if response.status_code == 200:
            content_disposition = response.headers.get('content-disposition')
            if content_disposition:
                filename = content_disposition.split('filename=')[1]
            else:
                filename = f'{md5sum}_results.zip'

            result_dir = self.DOWNLOAD_DIR

            # Save the file with the extracted or default filename
            logging.info('Downloading results...')
            file_path = os.path.join(result_dir, filename)
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)

            logging.info(
                f'Finished downloading results. \n Stored at {os.path.abspath(file_path)}'
            )
        else:
            logging.warning(
                f"Unexpected response when downloading: {response.status_code}"
            )
            check_response_code(response=response, successfull_opt="")
