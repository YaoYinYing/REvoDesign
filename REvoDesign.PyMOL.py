import os

print(f'REvoDesign UI is installed in {os.path.dirname(__file__)}')

def install_via_pip(source='https://github.com/YaoYinYing/REvoDesign'):
    import sys, subprocess
    print('Installation is started. This may take a while and the window will freeze until it is done.')
    python_exe = os.path.realpath(sys.executable)
    # install via pip+git
    result = subprocess.run(
        [python_exe, '-m', 'pip', 'install', f'git+{source}'],
        check=True,
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
cmd.extend('install_REvoDesign_via_pip',install_via_pip)

try:
    from REvoDesign import REvoDesignPlugin
except ImportError:
    try:
        install_via_pip()
        print('Installation succeeded. ')
        from REvoDesign import REvoDesignPlugin
    except ImportError:
        print('Installation failed. You can still use the following in PyMOL command prompt to install REvoDesign manually.')
        print('`install_REvoDesign_via_pip https://github.com/YaoYinYing/REvoDesign` or ')
        print('`install_REvoDesign_via_pip file:///local/path/to/repository/of/REvoDesign`')
    


# entrypoint of PyMOL plugin
def __init_plugin__(app=None):
    '''
    Add an entry to the PyMOL "Plugin" menu
    '''
    from pymol.plugins import addmenuitemqt

    plugin = REvoDesignPlugin()
    addmenuitemqt('REvoDesign', plugin.run_plugin_gui)
