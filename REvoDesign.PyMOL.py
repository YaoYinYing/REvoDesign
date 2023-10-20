import sys,os
import absl.logging as logging

logging.set_verbosity(logging.DEBUG)
logging.info(f'REvoDesign UI is installed in {os.path.dirname(__file__)}')

sys.path.append(os.path.dirname(__file__))

from revodesign import REvoDesignPlugin

# entrypoint of PyMOL plugin
def __init_plugin__(app=None):
    
    '''
    Add an entry to the PyMOL "Plugin" menu
    '''
    from pymol.plugins import addmenuitemqt
    plugin = REvoDesignPlugin()
    addmenuitemqt('REvoDesign', plugin.run_plugin_gui)

