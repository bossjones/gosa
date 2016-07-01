# This file is part of the GOsa framework.
#
#  http://gosa-project.org
#
# Copyright:
#  (C) 2016 GONICUS GmbH, Germany, http://www.gonicus.de
#
# See the LICENSE file in the project's top-level directory for details.

import pytest
from gosa.backend.components.jsonrpc_objects import JSONRPCObjectMapper, ObjectRegistry
from tests.GosaTestCase import GosaTestCase

class JSONRPCObjectMapperTestCase(GosaTestCase):

    def setUp(self):
        super(JSONRPCObjectMapperTestCase, self).setUp()
        self.mapper = JSONRPCObjectMapper()

    # def test_listObjectOIDs(self):
    #     objectRegistry = ObjectRegistry.getInstance()
    #     objectRegistry.register('test.oid', unittest.mock.MagicMock())
    #     res = self.mapper.listObjectOIDs()
    #     assert 'test.oid' in res
    #     assert len(res) == 1

    def test_openObject(self):
        res = self.mapper.openObject('admin','object','dc=example,dc=net')
        assert res['dc'] == "example"

        with pytest.raises(Exception):
            self.mapper.openObject('admin', 'object', 'dc=example,dc=net')


    def test_closeObject(self):
        res = self.mapper.openObject('admin', 'object', 'dc=example,dc=net')

        with pytest.raises(ValueError):
            self.mapper.closeObject('admin','unknown')

        with pytest.raises(ValueError):
            self.mapper.closeObject('someone else', res["__jsonclass__"][1][1])

        self.mapper.closeObject('admin', res["__jsonclass__"][1][1])

        # as a workaround for checking if its not loaded anymore we try to reload it
        with pytest.raises(ValueError):
            self.mapper.reloadObject('admin', res["__jsonclass__"][1][1])


    def test_getObjectProperty(self):
        res = self.mapper.openObject('admin', 'object', 'dc=example,dc=net')
        ref = res["__jsonclass__"][1][1]

        with pytest.raises(ValueError):
            self.mapper.getObjectProperty('admin', 'unknown', 'prop')

        with pytest.raises(ValueError):
            self.mapper.getObjectProperty('admin', ref, 'prop')

        with pytest.raises(ValueError):
            self.mapper.getObjectProperty('someone else', ref, 'description')

        assert self.mapper.getObjectProperty('admin', ref, 'description') == "Example"


    def test_setObjectProperty(self):
        res = self.mapper.openObject('admin', 'object', 'dc=example,dc=net')
        ref = res["__jsonclass__"][1][1]

        with pytest.raises(ValueError):
            self.mapper.setObjectProperty('admin', 'unknown', 'prop', 'val')

        with pytest.raises(ValueError):
            self.mapper.setObjectProperty('admin', ref, 'prop', 'val')

        with pytest.raises(ValueError):
            self.mapper.setObjectProperty('someone else', ref, 'description', 'val')

        self.mapper.setObjectProperty('admin', ref, 'description', 'val')
        assert self.mapper.getObjectProperty('admin', ref, 'description') == "val"

        #undo
        self.mapper.setObjectProperty('admin', ref, 'description', 'Example')
        assert self.mapper.getObjectProperty('admin', ref, 'description') == "Example"

    # Todo: Fix ObjectProxy.__init__ call with uuid (as _id)
    # def test_reloadObjectProperty(self):
    #     res = self.mapper.openObject('admin', 'object', 'dc=example,dc=net')
    #     uuid = res['uuid']
    #     ref = res["__jsonclass__"][1][1]
    #
    #     with pytest.raises(ValueError):
    #         self.mapper.reloadObject('someone else', ref)
    #
    #     res = self.mapper.reloadObject('admin', ref)
    #     assert uuid != res['uuid']