import os
import os.path
from datetime import date, datetime
import tempfile

import pytest
import github

import private_pypi
from private_pypi.pkg_repos import (
        GitHubConfig,
        GitHubAuthToken,
        LocalPaths,
        GitHubPkgRepo,
        load_pkg_repo_configs,
        create_pkg_repo,
)
from private_pypi.utils import read_toml, write_toml


# http://doc.pytest.org/en/latest/example/markers.html
def pytest_addoption(parser):
    parser.addoption("--run-backend-github", action="store_true")
    parser.addoption("--run-slow-test", action="store_true")


def pytest_configure(config):
    config.addinivalue_line("markers", "backend_github: test github workflow.")
    config.addinivalue_line("markers", "slow_test: takes long time to run.")


def pytest_runtest_setup(item):
    marked_backend_github = False
    marked_slow_test = False

    # Mark manually.
    for marker in item.iter_markers():
        if marker.name == 'backend_github':
            marked_backend_github = True
        elif marker.name == 'slow_test':
            marked_slow_test = True

    # Mark automatically.
    if 'setup_test_github_repo' in item.fixturenames:
        marked_backend_github = True
    if 'empty_github_pkg_repo' in item.fixturenames:
        marked_backend_github = True
    if 'dirty_github_pkg_repo' in item.fixturenames:
        marked_backend_github = True
    if 'preset_github_pkg_repo' in item.fixturenames:
        marked_backend_github = True
    if 'preset_workflow_args' in item.fixturenames:
        marked_backend_github = True

    if marked_backend_github and not item.config.option.run_backend_github:
        pytest.skip("Skip github backend test.")
    if marked_slow_test and not item.config.option.run_slow_test:
        pytest.skip("Skip slow test.")


def setup_test_github_repo():
    """Create a github repository for test session.
    """
    gh_token = os.getenv('TEST_GITHUB_TOKEN')
    assert gh_token

    gh_client = github.Github(gh_token)
    gh_user = gh_client.get_user()

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    description = (
            'Autogen test repo for the project python-best-practices/private-pypi '
            f'({private_pypi.__doc__} homepage https://github.com/python-best-practices/private-pypi), '
            f'created by user {gh_user.login}. ')
    repo_name = f'private-pypi-test-{timestamp}'
    gh_user.create_repo(
            name=repo_name,
            description=description,
            homepage='https://github.com/python-best-practices/private-pypi',
            has_issues=False,
            has_wiki=False,
            has_downloads=False,
            has_projects=False,
            auto_init=True,
    )

    # owner, repo, token
    return gh_user.login, repo_name, gh_token


def create_github_pkg_repo_for_test(name):
    owner, repo, token = setup_test_github_repo()
    return GitHubPkgRepo(
            config=GitHubConfig(name=name, owner=owner, repo=repo, large_package_bytes=512),
            secret=GitHubAuthToken(name=name, raw=token),
            local_paths=LocalPaths(
                    stat=str(tempfile.mkdtemp()),
                    cache=str(tempfile.mkdtemp()),
            ),
    )


@pytest.fixture(scope='function')
def empty_github_pkg_repo():
    yield create_github_pkg_repo_for_test('empty_github_test')


@pytest.fixture(scope='session')
def dirty_github_pkg_repo():
    yield create_github_pkg_repo_for_test('dirty_github_test')


def create_github_auth_token():
    gh_token = os.getenv('TEST_GITHUB_TOKEN')
    assert gh_token
    return GitHubAuthToken(name='test_github_token', raw=gh_token)


@pytest.fixture(scope='session')
def preset_github_pkg_repo():
    pkg_repo_configs = load_pkg_repo_configs('tests/fixtures/preset_config.toml')
    yield create_pkg_repo(
            config=pkg_repo_configs['preset_github_test'],
            secret=create_github_auth_token(),
            local_paths=LocalPaths(
                    stat=str(tempfile.mkdtemp()),
                    cache=str(tempfile.mkdtemp()),
            ),
    )


@pytest.fixture(scope='session')
def preset_workflow_args():
    args = {
            'pkg_repo_config_file': 'tests/fixtures/preset_config.toml',
            'index_folder': tempfile.mkdtemp(),
            'stat_folder': tempfile.mkdtemp(),
            'cache_folder': tempfile.mkdtemp(),
            'admin_pkg_repo_secret_file': None,
    }
    preset_github_test_index = read_toml('tests/fixtures/preset_github_test_index.toml')
    write_toml(os.path.join(args['index_folder'], 'preset_github_test.index'),
               preset_github_test_index)
    yield args


def create_random_file(path, size):
    with open(path, 'wb') as fout:
        fout.write(os.urandom(size))
    return path
