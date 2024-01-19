'''
Described at GitHub:
https://github.com/YaoYinYing/REvoDesign

Authors : Yinying Yao
Program : REvoDesign
Date    : Sept 2023

REvoDesign -- Makes enzyme redesign tasks easier to all.
'''
import os

print(f'REvoDesign entrypoint is located at {os.path.dirname(__file__)}')

install_msg = '''
You can still use the following in PyMOL command prompt to install REvoDesign manually:\n
`install_REvoDesign_via_pip` or \n
`install_REvoDesign_via_pip file:///local/path/to/repository/of/REvoDesign`\n
After it is done, you should restart PyMOL.
'''

REPO_URL='https://github.com/YaoYinYing/REvoDesign'

def install_via_pip(
    source=REPO_URL,
    upgrade=0,
    vebose=1,
    extras='',
):
    def get_source_and_tag(source):
        git_dir=source.split('@')[0]
        if '@' in source:
            git_tag=source.split('@')[1]
        else:
            git_tag=''
        return git_dir, git_tag
    
    import sys, subprocess

    upgrade = int(upgrade)
    verbose = int(verbose)

    print(
        'Installation is started. This may take a while and the window will freeze until it is done.'
    )
    python_exe = os.path.realpath(sys.executable)

    
    # use default source
    if not source:
        source=REPO_URL

    git_url,git_tag=get_source_and_tag(source=source)
    package_string=f"REvoDesign{f'[{extras}]' if extras and extras in ['jax', 'tf','torch', 'full'] else ''}"
    
    # with github url and tag
    if source and source.startswith('https://'):
        package_string += f' @ git+{git_url}{f"@{git_tag}" if git_tag else ""}'

    # with git repo clone and tag
    elif source.startswith('file://'):
        if not os.path.exists(os.path.join(git_url, '.git')):
            raise FileNotFoundError(f'Git dir not found: {os.path.join(git_url, ".git")}')
        package_string += f' @ git+{source}{f"@{git_tag}" if git_tag else ""}'

    # with unzipped code dir
    elif os.path.exists(source) and os.path.isdir(source):
        if not os.path.exists(os.path.join(source,'pyproject.toml')):
            raise FileNotFoundError(f'{source} is not a directory containing pyproject.toml')
        if git_tag:
            raise ValueError('unzipped code directory can not have a tag!')
        if source.endswith('/'):
            source=source[:-1]
        package_string = f"{source}{f'[{extras}]'if extras else ''}"

    # with zipped code archive
    elif os.path.exists(source) and os.path.isfile(source):
        if git_tag:
            raise ValueError('zipped file can not have a tag!')
        
        if source.endswith('.zip'):
            package_string = source
        elif source.endswith('.tar.gz'):
            package_string += f'@{source}'
        else:
            raise FileNotFoundError(f'{source} is neither a zipped file nor a tar.gz file!')
        
        
    else:
        raise ValueError(f'Unknown installation source {source}!')


    # run installation via pip
    subprocess.run([python_exe, '-m', 'ensurepip'])

    pip_cmd = [
        python_exe,
        '-m',
        'pip',
        'install',
        f"{package_string}",
    ]

    if upgrade:
        pip_cmd.append('--upgrade')

    print(pip_cmd)

    result = subprocess.run(
        pip_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        print(f'Installation failed: {source}')
        if vebose:
            print(f'stdout: {result.stdout.decode()}')
            print(f'stderr: {result.stderr.decode()}')
    else:
        print(
            f'Installation succeeded: {source}',
        )
        if vebose:
            print(f'stdout: {result.stdout.decode()}')
        print(
            'If this is an upgrade, please restart PyMOL for it to take effect.'
        )


from pymol import cmd
import traceback

cmd.extend('install_REvoDesign_via_pip', install_via_pip)

try:
    from REvoDesign import REvoDesignPlugin
except ImportError:
    print('Installation failed. ')
    print(install_msg)


# entrypoint of PyMOL plugin
def __init_plugin__(app=None):
    '''
    Add an entry to the PyMOL "Plugin" menu
    '''
    from pymol.plugins import addmenuitemqt

    try:
        from REvoDesign import REvoDesignPlugin

        plugin = REvoDesignPlugin()
        addmenuitemqt('REvoDesign', plugin.run_plugin_gui)
    except ImportError:
        traceback.print_exc()
        print('REvoDesign is not available.')
        print(install_msg)
