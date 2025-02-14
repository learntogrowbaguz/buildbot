# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from parameterized import parameterized
from twisted.trial import unittest

from buildbot.test.util import config
from buildbot.util.git import GitMixin
from buildbot.util.git import check_ssh_config
from buildbot.util.git import ensureSshKeyNewline
from buildbot.util.git import escapeShellArgIfNeeded
from buildbot.util.git import getSshKnownHostsContents
from buildbot.util.git import scp_style_to_url_syntax


class TestEscapeShellArgIfNeeded(unittest.TestCase):
    def assert_escapes(self, arg):
        escaped = f'"{arg}"'
        self.assertEqual(escapeShellArgIfNeeded(arg), escaped)

    def assert_does_not_escape(self, arg):
        self.assertEqual(escapeShellArgIfNeeded(arg), arg)

    def test_empty(self):
        self.assert_escapes('')

    def test_spaces(self):
        self.assert_escapes(' ')
        self.assert_escapes('a ')
        self.assert_escapes(' a')
        self.assert_escapes('a b')

    def test_special(self):
        self.assert_escapes('a=b')
        self.assert_escapes('a%b')
        self.assert_escapes('a(b')
        self.assert_escapes('a[b')

    def test_no_escape(self):
        self.assert_does_not_escape('abc')
        self.assert_does_not_escape('a_b')
        self.assert_does_not_escape('-opt')
        self.assert_does_not_escape('--opt')


class TestSetUpGit(unittest.TestCase, config.ConfigErrorsMixin):
    @parameterized.expand([
        ('no_keys', None, None, None, None),
        ('only_private_key', 'key', None, None, None),
        ('private_key_host_key', 'key', 'host', None, None),
        ('private_key_known_hosts', 'key', None, 'hosts', None),
        (
            'no_private_key_host_key',
            None,
            'host',
            None,
            'sshPrivateKey must be provided in order use sshHostKey',
        ),
        (
            'no_private_key_known_hosts',
            None,
            None,
            'hosts',
            'sshPrivateKey must be provided in order use sshKnownHosts',
        ),
        (
            'both_host_key_known_hosts',
            'key',
            'host',
            'hosts',
            'only one of sshKnownHosts and sshHostKey can be provided',
        ),
    ])
    def test_config(self, name, private_key, host_key, known_hosts, config_error):
        if config_error is None:
            check_ssh_config(
                'TestSetUpGit',
                private_key,
                host_key,
                known_hosts,
            )
        else:
            with self.assertRaisesConfigError(config_error):
                check_ssh_config(
                    'TestSetUpGit',
                    private_key,
                    host_key,
                    known_hosts,
                )


class TestParseGitFeatures(GitMixin, unittest.TestCase):
    def setUp(self):
        self.setupGit()

    def test_no_output(self):
        self.parseGitFeatures('')
        self.assertFalse(self.gitInstalled)
        self.assertFalse(self.supportsBranch)
        self.assertFalse(self.supportsSubmoduleForce)
        self.assertFalse(self.supportsSubmoduleCheckout)
        self.assertFalse(self.supportsSshPrivateKeyAsEnvOption)
        self.assertFalse(self.supportsSshPrivateKeyAsConfigOption)
        self.assertFalse(self.supports_lsremote_symref)
        self.assertFalse(self.supports_credential_store)

    def test_git_noversion(self):
        self.parseGitFeatures('git')
        self.assertFalse(self.gitInstalled)
        self.assertFalse(self.supportsBranch)
        self.assertFalse(self.supportsSubmoduleForce)
        self.assertFalse(self.supportsSubmoduleCheckout)
        self.assertFalse(self.supportsSshPrivateKeyAsEnvOption)
        self.assertFalse(self.supportsSshPrivateKeyAsConfigOption)
        self.assertFalse(self.supports_lsremote_symref)
        self.assertFalse(self.supports_credential_store)

    def test_git_zero_version(self):
        self.parseGitFeatures('git version 0.0.0')
        self.assertTrue(self.gitInstalled)
        self.assertFalse(self.supportsBranch)
        self.assertFalse(self.supportsSubmoduleForce)
        self.assertFalse(self.supportsSubmoduleCheckout)
        self.assertFalse(self.supportsSshPrivateKeyAsEnvOption)
        self.assertFalse(self.supportsSshPrivateKeyAsConfigOption)
        self.assertFalse(self.supports_lsremote_symref)
        self.assertFalse(self.supports_credential_store)

    def test_git_2_10_0(self):
        self.parseGitFeatures('git version 2.10.0')
        self.assertTrue(self.gitInstalled)
        self.assertTrue(self.supportsBranch)
        self.assertTrue(self.supportsSubmoduleForce)
        self.assertTrue(self.supportsSubmoduleCheckout)
        self.assertTrue(self.supportsSshPrivateKeyAsEnvOption)
        self.assertTrue(self.supportsSshPrivateKeyAsConfigOption)
        self.assertTrue(self.supports_lsremote_symref)
        self.assertTrue(self.supports_credential_store)


class TestAdjustCommandParamsForSshPrivateKey(GitMixin, unittest.TestCase):
    def test_throws_when_wrapper_not_given(self):
        self.gitInstalled = True

        command = []
        env = {}
        with self.assertRaises(RuntimeError):
            self.setupGit()
            self.adjustCommandParamsForSshPrivateKey(command, env, 'path/to/key')


class TestGetSshKnownHostsContents(unittest.TestCase):
    def test(self):
        key = 'ssh-rsa AAAA<...>WsHQ=='

        expected = '* ssh-rsa AAAA<...>WsHQ=='
        self.assertEqual(expected, getSshKnownHostsContents(key))


class TestensureSshKeyNewline(unittest.TestCase):
    def setUp(self):
        self.sshGoodPrivateKey = """-----BEGIN SSH PRIVATE KEY-----
base64encodedkeydata
-----END SSH PRIVATE KEY-----
"""
        self.sshMissingNewlinePrivateKey = """-----BEGIN SSH PRIVATE KEY-----
base64encodedkeydata
-----END SSH PRIVATE KEY-----"""

    def test_good_key(self):
        """Don't break good keys"""
        self.assertEqual(self.sshGoodPrivateKey, ensureSshKeyNewline(self.sshGoodPrivateKey))

    def test_missing_newline(self):
        """Add missing newline to stripped keys"""
        self.assertEqual(
            self.sshGoodPrivateKey, ensureSshKeyNewline(self.sshMissingNewlinePrivateKey)
        )


class TestScpStyleToUrlSyntax(unittest.TestCase):
    @parameterized.expand([
        ('normal_url', 'ssh://path/to/git', 'ssh://path/to/git'),
        ('unix_path', '/path/to/git', '/path/to/git'),
        ('windows_path', 'C:\\path\\to\\git', 'C:\\path\\to\\git'),
        ('scp_path', 'host:path/to/git', 'ssh://host:23/path/to/git'),
    ])
    def test(self, name, url, expected):
        self.assertEqual(scp_style_to_url_syntax(url, port=23), expected)
