import tornado.web
import pkg_resources
from gosa.common import Environment
from gosa.common.hsts_request_handler import HSTSStaticFileHandler


class StaticHandler(HSTSStaticFileHandler):

    def initialize(self):
        path = pkg_resources.resource_filename("gosa.backend", "data/templates")
        super(StaticHandler, self).initialize(path)


class ImageHandler(HSTSStaticFileHandler):

    def initialize(self):
        env = Environment.getInstance()
        path = env.config.get("user.image-path", "/var/lib/gosa/images")
        super(ImageHandler, self).initialize(path)
