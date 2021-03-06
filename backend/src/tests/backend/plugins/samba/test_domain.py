# This file is part of the GOsa framework.
#
#  http://gosa-project.org
#
# Copyright:
#  (C) 2016 GONICUS GmbH, Germany, http://www.gonicus.de
#
# See the LICENSE file in the project's top-level directory for details.

from unittest import TestCase, mock
import pytest
from gosa.backend.plugins.samba.domain import *

class SambaGuiMethodsTestCase(TestCase):

    @mock.patch.object(Environment, "getInstance")
    @mock.patch.object(PluginRegistry, 'getInstance')
    def test_getSambaPassword(self, mockedRegistry, mockedEnv):

        # mockup ACL resolver
        mockedRegistry.return_value.check.return_value = True

        # mockup the environment
        mockedEnv.return_value.domain = "testdomain"

        with mock.patch('gosa.backend.plugins.samba.domain.ObjectProxy', autoSpec=True, create=True) as m:
            # run the test
            user = m.return_value
            methods = SambaGuiMethods()
            methods.setSambaPassword("username", "dn", "password")
            assert user.sambaNTPassword is not None
            assert user.sambaLMPassword is not None
            assert user.commit.called is True
            assert m.called is True

        # test with ACL.check for sambaNTPassword is False
        mockedRegistry.return_value.check.return_value = False

        with mock.patch('gosa.backend.plugins.samba.domain.ObjectProxy', create=True):
            # run the test
            methods = SambaGuiMethods()
            with pytest.raises(ACLException):
                methods.setSambaPassword("username", "dn", "password")

        # test with ACL.check for sambaLMPassword is False
        def check(user, topic, flags, base):
            return not topic == "testdomain.objects.User.attributes.sambaLMPassword"
        mockedRegistry.return_value.check.side_effect = check

        with mock.patch('gosa.backend.plugins.samba.domain.ObjectProxy', create=True):
            # run the test
            methods = SambaGuiMethods()
            with pytest.raises(ACLException):
                methods.setSambaPassword("username", "dn", "password")

    @mock.patch.object(PluginRegistry, 'getInstance')
    def test_getSambaDomainInformation(self, mockedInstance):
        # mock the whole lookup in the ObjectIndex to return True
        mockedInstance.return_value.search.return_value = [{"sambaMinPwdLength": 6,
                                                            "sambaPwdHistoryLength": 10,
                                                            "sambaMaxPwdAge": 10,
                                                            "sambaMinPwdAge": 1,
                                                            "sambaLockoutDuration": 60,
                                                            "sambaRefuseMachinePwdChange": False,
                                                            "sambaLogonToChgPwd": True,
                                                            "sambaLockoutThreshold": 30,
                                                            "sambaBadPasswordTime": 2147483647}]

        methods = SambaGuiMethods()
        target = mock.MagicMock()
        target.sambaDomainName = 'DEFAULT'
        res = methods.getSambaDomainInformation("username", target)
        # this is just a check that the method is callable so we do not really check the output here
        assert len(res) > 0


@mock.patch.object(PluginRegistry, 'getInstance')
def test_IsValidSambaDomainName(mockedInstance):
    # mock the whole lookup in the ObjectIndex to return True
    mockedInstance.return_value.search.return_value = [1]

    check = IsValidSambaDomainName()

    (res, errors) = check.process(None, None, ["test"])
    assert res is True
    assert len(errors) == 0

    # mockup everything to return False
    mockedInstance.return_value.search.return_value = []

    (res, errors) = check.process(None, None, ["test"])
    assert res is False
    assert len(errors) == 1
