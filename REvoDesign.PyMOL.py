'''
Described at GitHub:
https://github.com/YaoYinYing/REvoDesign

Authors : Yinying Yao
Program : REvoDesign
Date    : Sept 2023

REvoDesign -- Makes enzyme redesign tasks easier to all.
'''
import os

print(f'REvoDesign UI is installed in {os.path.dirname(__file__)}')


def install_via_pip(
    source='https://github.com/YaoYinYing/REvoDesign', upgrade=0
):
    import sys, subprocess

    print(
        'Installation is started. This may take a while and the window will freeze until it is done.'
    )
    python_exe = os.path.realpath(sys.executable)

    _source = ''

    # a HTTP repo URL
    if source.startswith('https://'):
        _source = f'git+{source}'

    # Downloaded or cloned source code
    else:
        local_source_dir = os.path.abspath(source.replace('file://', ''))

        # Invalid path
        if not os.path.exists(local_source_dir):
            print(f'{local_source_dir} does not exist')
            return

        # Early return due to path offset.
        elif not os.path.exists(
            os.path.join(local_source_dir, 'pyproject.toml')
        ):
            print(
                f'{local_source_dir}.pyproject.toml does not exist. Please check the source code path.'
            )
            return

        # An repo clone that contains .git
        if os.path.exists(os.path.join(local_source_dir, '.git')):
            _source = f'git+file://{local_source_dir}'

        # An unzipped copy of source code with building file
        else:
            _source = f'git+{local_source_dir}'

    # install via pip+git
    subprocess.run([python_exe, '-m', 'ensurepip'])

    pip_cmd = [
        python_exe,
        '-m',
        'pip',
        'install',
        _source,
    ]
    if upgrade:
        pip_cmd.append('--upgrade')

    result = subprocess.run(
        pip_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        print(f'Installation failed: {source}')
        print(f'stdout: {result.stdout.decode()}')
        print(f'stderr: {result.stderr.decode()}')
    else:
        print(
            f'Installation succeeded: {source}',
        )
        print(f'stdout: {result.stdout.decode()}')


from pymol import cmd

cmd.extend('install_REvoDesign_via_pip', install_via_pip)

try:
    from REvoDesign import REvoDesignPlugin
except ImportError:
    print(
        'Installation failed. You can still use the following in PyMOL command prompt to install REvoDesign manually.'
    )
    print('`install_REvoDesign_via_pip` or ')
    print(
        '`install_REvoDesign_via_pip file:///local/path/to/repository/of/REvoDesign`'
    )
    print('After it is done, you should restart PyMOL.')


# entrypoint of PyMOL plugin
def __init_plugin__(app=None):
    '''
    Add an entry to the PyMOL "Plugin" menu
    '''
    from pymol.plugins import addmenuitemqt

    plugin = REvoDesignPlugin()
    addmenuitemqt('REvoDesign', plugin.run_plugin_gui)
