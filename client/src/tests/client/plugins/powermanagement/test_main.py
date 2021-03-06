# This file is part of the GOsa framework.
#
#  http://gosa-project.org
#
# Copyright:
#  (C) 2016 GONICUS GmbH, Germany, http://www.gonicus.de
#
# See the LICENSE file in the project's top-level directory for details.
import subprocess
import dbus
import dbusmock
import time
from unittest import mock
from gosa.client.plugins.powermanagement.main import *
from tests.dbus_test_case import ClientDBusTestCase


class ClientPowermanagementTestCase(ClientDBusTestCase):

    def setUp(self):
        (self.inv_mock, self.dbus_mock) = self.spawn_server_template('logind', stdout=subprocess.PIPE)

    def tearDown(self):
        self.inv_mock.terminate()
        self.inv_mock.wait()

    def test_shutdown(self):
        with mock.patch("gosa.client.plugins.notify.main.DBusRunner.get_instance") as m:
            m.return_value.get_system_bus.return_value = self.dbus_con
            inv = PowerManagement()
            time.sleep(0.3)
            inv.shutdown()
            self.assertRegex(self.inv_mock.stdout.readline(), b'^[0-9.]+ PowerOff True\n?$')

    def test_reboot(self):
        with mock.patch("gosa.client.plugins.notify.main.DBusRunner.get_instance") as m:
            m.return_value.get_system_bus.return_value = self.dbus_con
            inv = PowerManagement()
            time.sleep(0.3)
            inv.reboot()
            self.assertRegex(self.inv_mock.stdout.readline(), b'^[0-9.]+ Reboot True\n?$')

    def test_suspend(self):
        with mock.patch("gosa.client.plugins.notify.main.DBusRunner.get_instance") as m:
            m.return_value.get_system_bus.return_value = self.dbus_con
            inv = PowerManagement()
            time.sleep(0.3)
            inv.suspend()
            self.assertRegex(self.inv_mock.stdout.readline(), b'^[0-9.]+ Suspend True\n?$')

    def test_hibernate(self):
        with mock.patch("gosa.client.plugins.notify.main.DBusRunner.get_instance") as m:
            m.return_value.get_system_bus.return_value = self.dbus_con
            inv = PowerManagement()
            time.sleep(0.3)
            inv.hibernate()
            self.assertRegex(self.inv_mock.stdout.readline(), b'^[0-9.]+ Hibernate True\n?$')
