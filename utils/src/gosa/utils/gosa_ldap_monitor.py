#!/usr/bin/env python3
# This file is part of the GOsa framework.
#
#  http://gosa-project.org
#
# Copyright:
#  (C) 2016 GONICUS GmbH, Germany, http://www.gonicus.de
#
# See the LICENSE file in the project's top-level directory for details.

import os
from time import sleep
from datetime import datetime
from lxml import etree
from base64 import b64decode
from gosa.common import Environment
from gosa.common.event import EventMaker
from gosa.common.components.mqtt_handler import MQTTHandler


def tail(path, initially_failed=False):
    # Start listening from the end of the given path
    if not initially_failed:
        path.seek(0, 2)

    # Try to read until something new pops up
    while True:
        line = path.readline()

        if not line:
            sleep(0.1)
            continue

        yield line.strip()


def monitor(path, modifier, proxy, initially_failed=False):
    # Initialize dn, timestamp and change type.
    dn = None
    ts = None
    ct = None

    try:
        with open(path, encoding='utf-8', errors='ignore') as f:

            # Collect lines until a newline occurs, fill
            # dn, ts and ct accordingly. Entries that only
            # change administrative values.
            for line in tail(f, initially_failed):

                # Catch dn
                if line.startswith("dn::"):
                    dn = b64decode(line[5:]).decode('utf-8')
                    continue

                elif line.startswith("dn:"):
                    dn = line[4:]
                    continue

                # Catch modifyTimestamp
                if line.startswith("modifyTimestamp:"):
                    ts = line[17:]
                    continue

                # Catch changetype
                if line.startswith("changetype:"):
                    ct = line[12:]
                    continue

                # Check modifiers name and if it's the
                # gosa-backend who triggered the change,
                # just reset the DN, because we don't need
                # to propagate this change.
                if line.startswith("modifiersName:"):
                    print("%s == %s" % (line[14:].lower(), modifier.lower()))
                    if line[14:].lower() == modifier.lower():
                        dn = None
                    continue

                # Trigger on newline.
                if line == "":
                    if dn:
                        if not ts:
                            ts = datetime.now().strftime("%Y%m%d%H%M%SZ")

                        e = EventMaker()
                        update = e.Event(
                            e.BackendChange(
                                e.DN(dn),
                                e.ModificationTime(ts),
                                e.ChangeType(ct)
                            )
                        )

                        proxy.send_event(update, topic="%s/events" % Environment.getInstance().domain)

                    dn = ts = ct = None

    except Exception as e:
        print("Error:", str(e))


def main():  # pragma: nocover
    env = Environment.getInstance()
    config = env.config

    # Load configuration
    path = config.get('backend-monitor.audit-log', default='/var/lib/gosa/ldap-audit.log')
    modifier = config.get('backend-monitor.modifier')

    # Connect to MQTT BUS
    proxy = MQTTHandler()

    # Main loop
    initially_failed = False
    while True:
        sleep(1)

        # Wait for file to pop up
        if not os.path.exists(path):
            initially_failed = True
            continue

        # Wait for file to be file
        if not os.path.isfile(path):
            initially_failed = True
            continue

        # Check if it is effectively readable
        try:
            with open(path):
                pass
        except IOError:
            initially_failed = True
            continue

        # Listen for changes
        monitor(path, modifier, proxy, initially_failed)


if __name__ == "__main__":  # pragma: nocover
    try:
        main()
    except KeyboardInterrupt:
        pass
