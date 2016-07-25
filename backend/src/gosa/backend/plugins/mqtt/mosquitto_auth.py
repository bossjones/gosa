# This file is part of the GOsa project.
#
#  http://gosa-project.org
#
# Copyright:
#  (C) 2016 GONICUS GmbH, Germany, http://www.gonicus.de
#
# See the LICENSE file in the project's top-level directory for details.
import logging
import re
from gosa.common import Environment
import tornado.web
from gosa.backend.utils.ldap import check_auth


class BaseMosquittoClass(tornado.web.RequestHandler):
    def __init__(self, application, request, **kwargs):
        super(BaseMosquittoClass, self).__init__(application, request, **kwargs)
        self.env = Environment.getInstance()
        self.log = logging.getLogger(__name__)

    def initialize(self):
        self.set_header('Content-Type', 'text/plain')
        self.set_header('Cache-Control', 'no-cache')

    def send_result(self, result):
        if result is True:
            self.set_status(200)
        else:
            self.set_status(403)
        self.finish('')

    def check_xsrf_cookie(self):  # pragma: nocover
        pass

    def data_received(self, chunk):  # pragma: nocover
        pass


class MosquittoAuthHandler(BaseMosquittoClass):
    """
    Handles Mosquitto auth plugins http authentification requests and checks them against ldap
    """

    def post(self, *args, **kwargs):
        username = self.get_argument('username', '')
        password = self.get_argument('password')

        self.send_result(check_auth(username, password))


class MosquittoAclHandler(BaseMosquittoClass):
    """
    Handles Mosquitto auth plugins http authorization (ACL) requests
    """

    def post(self, *args, **kwargs):
        """
        Handle incoming acl post request from the mosquitto auth plugin.
        Available parameters are:
            username: current username
            topic: mqtt topic
            clientid: client id
            acc (1 == subscribe, 2 == publish)
        """
        uuid = self.get_argument('username', '')
        topic    = self.get_argument('topic')
        acc      = self.get_argument('acc') # 1 == SUB, 2 == PUB

        client_channel = "%s/client/%s" % (self.env.domain, uuid)

        if topic == "%s/client/broadcast" % self.env.domain:
            # listen on client broadcast channel
            self.send_result(acc == "1")
        elif topic == client_channel or topic.startswith(client_channel):
            # our own channel -> everything goes
            self.send_result(True)
        else:
            self.send_result(False)


class MosquittoSuperuserHandler(BaseMosquittoClass):
    """
    Handles Mosquitto auth plugins http superuser authentification requests
    """

    def __init__(self, application, request, **kwargs):
        super(MosquittoSuperuserHandler, self).__init__(application, request, **kwargs)
        admins = self.env.config.get("backend.admins", default=None)
        self.admins = []
        if admins:
            admins = re.sub(r'\s', '', admins)
            self.admins = admins.split(",")

    def post(self, *args, **kwargs):

        username = self.get_argument('username', '')
        #self.send_result(username in self.admins)
        self.send_result(False)