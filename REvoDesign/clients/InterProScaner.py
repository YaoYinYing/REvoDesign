'''
An rewriten class based on the official REST API script.
Doc: https://www.ebi.ac.uk/seqdb/confluence/display/JDSAT/InterProScan+5+Help+and+Documentation#InterProScan5HelpandDocumentation-RESTAPI
Code: https://raw.githubusercontent.com/ebi-wp/webservice-clients/master/python/iprscan5.py
'''

import os
import platform
import time
import requests
from lxml import etree
from absl import logging


class InterProScanner:
    def __init__(self):
        self.base_url = 'https://www.ebi.ac.uk/Tools/services/rest/iprscan5'

        self.email = ''
        self.title = ''
        self.sequence = ''

        self.version = '2023-05-12 14:28'
        self.pwd = os.getcwd()

        self.poll_freq = 3
        self.output_level = 1
        self.debug_level = 0

        self.outfile = None
        self.outformat = None
        self.async_job = False
        self.job_id = None

    def service_run(self, params):
        user_agent = self.get_user_agent()
        self.http_headers = {'User-Agent': user_agent}
        request_url = f"{self.base_url}/run/"
        logging.info(f"Request URL: {request_url}")
        response = requests.post(
            request_url, data=params, headers=self.http_headers
        )
        response_text = response.text
        print(response_text)
        if response_text.startswith('iprscan5-'):
            self.job_id = response_text

    def service_get_status(self, job_id):
        request_url = f"{self.base_url}/status/{job_id}"
        logging.info(f"Request URL: {request_url}")
        response = requests.get(request_url)
        status = response.text
        print(status)
        return status

    def service_get_result_types(self, job_id):
        logging.info('Begin service_get_result_types')
        logging.info('job_id: %s', job_id)

        request_url = f'{self.base_url}/resulttypes/{job_id}'
        logging.info('request_url: %s', request_url)

        response = requests.get(request_url)

        if response.status_code == 200:
            result_types = []
            xml_data = response.content

            # Parse the XML response using lxml
            root = etree.fromstring(xml_data)

            for result_type in root.findall('type'):
                logging.debug(
                    f"{result_type.find('identifier').text} - {result_type.find('description').text if result_type.find('description') is not None else None}"
                )
                result_types.append(result_type.find('identifier').text)

            logging.info('End service_get_result_types')
            return result_types
        else:
            logging.warning(
                'Error: Failed to get result types. Status code: %d',
                response.status_code,
            )
            return []

    def get_user_agent(self):
        urllib_agent = f'Python-urllib/{requests.__version__}'
        client_revision = self.version
        user_agent = (
            f'EBI-Sample-Client/{client_revision} ({os.path.basename(__file__)} '
            f'Python {platform.python_version()}; {platform.system()}) {urllib_agent}'
        )
        return user_agent

    def submit_job(self):
        self.params = {
            'email': self.email,
            'title': self.title,
            'sequence': self.sequence,  # Include other required parameters
        }

        response_text = self.service_run(self.params)
        if self.async_job:
            logging.info(response_text)
            logging.info(
                "To check status: python %s --status --jobid %s"
                "" % (os.path.basename(__file__), self.job_id)
            )
        else:
            self.poll_job()

    def poll_job(self):
        while True:
            status = self.service_get_status(self.job_id)
            logging.info(status)
            if status != 'QUEUED' and status != 'RUNNING':
                break
            time.sleep(self.poll_freq)

        self.get_results()

    def get_results(self):
        result_types = self.service_get_result_types(self.job_id)
        for result_type in result_types:
            if not self.outformat or self.outformat == result_type:
                self.retrieve_result(result_type)

    def retrieve_result(self, result_type):
        request_url = f"{self.base_url}/result/{self.job_id}/{result_type}"
        response = requests.get(request_url)
        result = response.content
        filename = self.get_result_filename(result_type)
        with open(os.path.join(self.pwd, filename), 'wb') as file:
            file.write(result)
        logging.info(f"Creating result file: {filename}")

    def get_result_filename(self, result_type):
        if self.outfile:
            filename = f"{self.outfile}.{result_type}"
        else:
            filename = f"{self.job_id}.{result_type}"
        return filename


if __name__ == '__main__':
    logging.info('Starting InterProScanner...')
    scanner = InterProScanner()
    # Set the class variables accordingly
    scanner.email = 'your_email@example.com'
    scanner.title = 'Protein Analysis Job'
    scanner.sequence = 'protein_sequence_data'
    scanner.outformat = 'html'  # Set the desired output format (optional)
    scanner.async_job = True  # Set to True for asynchronous job

    scanner.submit_job()
