# This file is part of the GOsa framework.
#
#  http://gosa-project.org
#
# Copyright:
#  (C) 2016 GONICUS GmbH, Germany, http://www.gonicus.de
#
# See the LICENSE file in the project's top-level directory for details.

import uuid
import datetime
from types import FunctionType

from gosa.common.event import EventMaker
from zope.interface import implementer
from gosa.common.utils import N_
from gosa.common import Environment
from gosa.common.error import GosaErrorHandler as C, GosaException
from gosa.common.handler import IInterfaceHandler
from gosa.common.components import Command, PluginRegistry, ObjectRegistry, Plugin
from gosa.backend.objects import ObjectProxy


# Register the errors handled  by us
C.register_codes(dict(
    REFERENCE_NOT_FOUND=N_("Reference '%(ref)s' not found"),
    PROPERTY_NOT_FOUND=N_("Property '%(property)s' not found"),
    METHOD_NOT_FOUND=N_("Method '%(method)s' not found"),
    OBJECT_LOCKED=N_("Object '%(object)s' has been locked by '%(user)s' on %(when)s"),
    OID_NOT_FOUND=N_("Object OID '%(oid)s' not found"),
    NOT_OBJECT_OWNER=N_("Caller does not own the referenced object")
    ))

@implementer(IInterfaceHandler)
class JSONRPCObjectMapper(Plugin):
    """
    The *JSONRPCObjectMapper* is a GOsa backend plugin that implements a stack
    which can handle object instances. These can be passed via JSONRPC using
    the *__jsonclass__* helper attribute and allows remote proxies to emulate
    the object on the stack. The stack can hold objects that have been
    retrieved by their *OID* using the :class:`gosa.common.components.objects.ObjectRegistry`.

    Example::

        >>> from gosa.common.components import JSONServiceProxy
        >>> # Create connection to service
        >>> proxy = JSONServiceProxy('https://admin:secret@gosa.example.net/rpc')
        >>> pm = proxy.openObject('libinst.diskdefinition')
        >>> pm.getDisks()
        []
        >>> proxy.closeObject(str(pm))
        >>>

    This will indirectly use the object mapper on the agent side.
    """
    _target_ = 'core'
    _priority_ = 70
    __stack = None

    def __init__(self):
        self.env = Environment.getInstance()
        self.__stack = {}

    def serve(self):
        sched = PluginRegistry.getInstance("SchedulerService").getScheduler()
        sched.add_interval_job(self.__gc, minutes=10, tag='_internal', jobstore="ram")

    @Command(__help__=N_("List available object OIDs"))
    def listObjectOIDs(self):
        """
        Provide a list of domain wide available object OIDs.

        ``Return:`` list
        """
        return list(ObjectRegistry.objects.keys())

    @Command(needsUser=True, __help__=N_("Close object and remove it from stack"))
    def closeObject(self, user, ref):
        """
        Close an object by its reference. This will free the object on
        the agent side.

        ================= ==========================
        Parameter         Description
        ================= ==========================
        ref               UUID / object reference
        ================= ==========================
        """
        if not self.__get_ref(ref):
            raise ValueError(C.make_error("REFERENCE_NOT_FOUND", ref=ref))

        if not self.__check_user(ref, user):
            raise ValueError(C.make_error("NOT_OBJECT_OWNER"))

        del self.__stack[ref]

    @Command(needsUser=True, __help__=N_("Prevent an object from beeing automatically closed by an inactivity timeout"))
    def continueObjectEditing(self, user, ref):
        """
        Objects which have been opened but not edited for a certain amount of time are automatically closed by the backend.
        This command delays this behaviour by increasing the timeout.
        ================= ==========================
        Parameter         Description
        ================= ==========================
        ref               UUID / object reference
        """
        objdsc = self.__get_ref(ref)
        if not objdsc:
            raise ValueError(C.make_error("REFERENCE_NOT_FOUND", ref=ref))

        if not self.__check_user(ref, user):
            raise ValueError(C.make_error("NOT_OBJECT_OWNER"))

        objdsc['last_interaction'] = datetime.datetime.now()
        if 'mark_for_deletion' in objdsc:
            # as this object has been marked for deletion, we have to run the garbage collection
            # to remove this mark now
            self.__gc()

    @Command(needsUser=True, needsSession=True, __help__=N_("Check if an object references is still available"))
    def checkObjectRef(self, user, session_id, ref):
        """
        Objects which have been opened but not edited for a certain amount of time are automatically closed by the backend.
        This command delays this behaviour by increasing the timeout.
        ================= ==========================
        Parameter         Description
        ================= ==========================
        ref               UUID / object reference
        ================= ==========================

        ``Return``: boolean
        """
        objdsc = self.__get_ref(ref)
        if objdsc and objdsc['user'] == user:
            # update session-id, which might have changed and is needed to inform the user about object closing
            objdsc['session_id'] = session_id
            return True

        return False


    @Command(needsUser=True, __help__=N_("Set property for object on stack"))
    def setObjectProperty(self, user, ref, name, value):
        """
        Set a property on an existing stack object.

        ================= ==========================
        Parameter         Description
        ================= ==========================
        ref               UUID / object reference
        name              Property name
        value             Property value
        ================= ==========================
        """
        objdsc = self.__get_ref(ref)
        if not objdsc:
            raise ValueError(C.make_error("REFERENCE_NOT_FOUND", ref=ref))

        if not name in objdsc['object']['properties']:
            raise ValueError(C.make_error("PROPERTY_NOT_FOUND", property=name))

        if not self.__check_user(ref, user):
            raise ValueError(C.make_error("NOT_OBJECT_OWNER"))

        objdsc['last_interaction'] = datetime.datetime.now()
        if 'mark_for_deletion' in objdsc:
            # as this object has been marked for deletion, we have to run the garbage collection
            # to remove this mark now
            self.__gc()

        return setattr(objdsc['object']['object'], name, value)

    @Command(needsUser=True, __help__=N_("Get property from object on stack"))
    def getObjectProperty(self, user, ref, name):
        """
        Get a property of an existing stack object.

        ================= ==========================
        Parameter         Description
        ================= ==========================
        ref               UUID / object reference
        name              Property name
        ================= ==========================

        ``Return``: mixed
        """
        objdsc = self.__get_ref(ref)
        if not objdsc:
            raise ValueError(C.make_error("REFERENCE_NOT_FOUND", ref=ref))

        if not name in objdsc['object']['properties']:
            raise ValueError(C.make_error("PROPERTY_NOT_FOUND", property=name))

        if not self.__check_user(ref, user):
            raise ValueError(C.make_error("NOT_OBJECT_OWNER"))

        return getattr(objdsc['object']['object'], name)

    @Command(needsUser=True, needsSession=True, __help__=N_("Call method from object on stack"))
    def dispatchObjectMethod(self, user, session_id, ref, method, *args):
        """
        Call a member method of the referenced object.

        ================= ==========================
        Parameter         Description
        ================= ==========================
        ref               UUID / object reference
        method            Method name
        args              Arguments to pass to the method
        ================= ==========================

        ``Return``: mixed
        """
        objdsc = self.__get_ref(ref)
        if not objdsc:
            raise ValueError(C.make_error("REFERENCE_NOT_FOUND", ref=ref))

        if not method in objdsc['object']['methods']:
            raise ValueError(C.make_error("METHOD_NOT_FOUND", method=method))

        if not self.__check_user(ref, user):
            raise ValueError(C.make_error("NOT_OBJECT_OWNER"))

        return getattr(objdsc['object']['object'], method)(*args)

    @Command(needsUser=True, __help__=N_("Reloads the object"))
    def reloadObject(self, user, ref):
        """
        Opens a copy of the object given as ref and
        closes the original instance.
        """
        if ref in self.__stack:
            item = self.__stack[ref]

            if not self.__check_user(ref, user):
                raise ValueError(C.make_error("NOT_OBJECT_OWNER"))

            oid = item['object']['oid']
            uuid = item['object']['uuid']
            session_id = item['session_id']
            new_item = self.openObject(user, session_id, oid, uuid)

            # Close original ref and return the new one
            self.closeObject(user, ref)

            return new_item

        else:
            raise ValueError(C.make_error("REFERENCE_NOT_FOUND", ref=ref))

    @Command(needsUser=True, __help__=N_("Returns a delta of the reference currently in store and the data store"))
    def diffObject(self, user, ref):
        """
        Opens a copy of the object given as ref and
        returns a diff - if any.
        """
        if not ref in self.__stack:
            return None

        if not self.__check_user(ref, user):
            raise ValueError(C.make_error("NOT_OBJECT_OWNER"))

        # Load current object
        item = self.__stack[ref]
        current_obj = ObjectProxy(item['object']['dn'])

        # Load cache object
        cache_obj = item['object']['object']

        ##
        ## Generate delta
        ##
        delta = {'attributes': {'added': {}, 'removed': [], 'changed': {}}, 'extensions': {'added': [], 'removed': []}}

        # Compare extension list
        crnt_extensions = set(current_obj.get_object_info()['extensions'].items())
        cche_extensions = set(cache_obj.get_object_info()['extensions'].items())
        for _e, _s in crnt_extensions - cche_extensions:
            if _s:
                delta['extensions']['added'].append(_e)
            else:
                delta['extensions']['removed'].append(_e)

        # Compare attribute contents
        crnt_attributes = dict(filter(lambda x: x[1], current_obj.get_attribute_values()['value'].items()))
        cche_attributes = dict(filter(lambda x: x[1], cache_obj.get_attribute_values()['value'].items()))
        for _k, _v in crnt_attributes.items():
            if _k in cche_attributes:
                if _v != cche_attributes[_k]:
                    delta['attributes']['changed'][_k] = _v
            else:
                delta['attributes']['added'][_k] = _v

        for _k, _v in cche_attributes.items():
            if not _k in crnt_attributes:
                delta['attributes']['removed'].append(_k)

        return delta

    @Command(needsUser=True, __help__=N_("Removes the given object"))
    def removeObject(self, user, oid, *args, **kwargs):
        """
        Open object on the agent side and calls its remove method

        ================= ==========================
        Parameter         Description
        ================= ==========================
        oid               OID of the object to create
        args/kwargs       Arguments to be used when getting an object instance
        ================= ==========================

        ``Return``: True
        """

        # In case of "object" we want to check the lock
        if oid == 'object':
            lck = self.__get_lock(args[0])
            if lck:
                raise Exception(C.make_error("OBJECT_LOCKED", object=args[0],
                    user=lck['user'],
                    when=lck['created'].strftime("%Y-%m-%d (%H:%M:%S)")
                    ))

        # Use oid to find the object type
        obj_type = self.__get_object_type(oid)

        # Make object instance and store it
        kwargs['user'] = user
        obj = obj_type(*args, **kwargs)
        obj.remove()
        return True

    @Command(needsUser=True, needsSession=True, __help__=N_("Instantiate object and place it on stack"))
    def openObject(self, user, session_id, oid, *args, **kwargs):
        """
        Open object on the agent side. This creates an instance on the
        stack and returns an a JSON description of the object and it's
        values.

        ================= ==========================
        Parameter         Description
        ================= ==========================
        oid               OID of the object to create
        args/kwargs       Arguments to be used when getting an object instance
        ================= ==========================

        ``Return``: JSON encoded object description
        """

        # In case of "object" we want to check the lock
        if oid == 'object':
            lck = self.__get_lock(args[0])
            if lck and (not session_id or lck['user'] != user or lck['session_id'] != session_id):
                raise Exception(C.make_error("OBJECT_LOCKED", object=args[0],
                                             user=lck['user'],
                                             when=lck['created'].strftime("%Y-%m-%d (%H:%M:%S)")))

        env = Environment.getInstance()

        # Use oid to find the object type
        obj_type = self.__get_object_type(oid)
        methods, properties = self.__inspect(obj_type)

        # Load instance, fill with dummy stuff
        ref = str(uuid.uuid1())

        # Make object instance and store it
        kwargs['user'] = user
        obj = obj_type(*args, **kwargs)

        # Merge in methods that may be available later due to extending more addons
        methods += obj.get_all_method_names()

        # Add dynamic information - if available
        if hasattr(obj, 'get_attributes'):
            properties = properties + obj.get_attributes()
        if hasattr(obj, 'get_methods'):
            methods = methods + obj.get_methods()

        objdsc = {
            'oid': oid,
            'dn': obj.dn if hasattr(obj, 'dn') else None,
            'uuid': obj.uuid if hasattr(obj, 'uuid') else None,
            'object': obj,
            'methods': list(set(methods)),
            'properties': properties
        }

        self.__stack[ref] = {
            'user': user,
            'session_id': session_id,
            'object': objdsc,
            'created': datetime.datetime.now()
        }

        # Build property dict
        propvals = {}
        if properties:
            propvals = dict([(p, getattr(obj, p)) for p in properties])

        propvals['uuid'] = obj.uuid

        # Build result
        result = {"__jsonclass__": ["json.JSONObjectFactory", [obj_type.__name__, ref, obj.dn, oid, methods, properties]]}
        result.update(propvals)

        return result

    def __check_user(self, ref, user):
        for ref, item in self.__stack.items():
            if item['user'] == user:
                return True

        return False

    def __get_object_type(self, oid):
        if not oid in ObjectRegistry.objects:
            raise ValueError(C.make_error("OID_NOT_FOUND", oid=oid))

        return ObjectRegistry.objects[oid]['object']

    def __inspect(self, clazz):
        methods = []
        properties = []

        for part in dir(clazz):
            if part.startswith("_"):
                continue
            obj = getattr(clazz, part)
            if isinstance(obj, FunctionType):
                methods.append(part)
            if isinstance(getattr(type(clazz), part, None), property):
                properties.append(part)

        return methods, properties

    def __get_ref(self, ref):
        return self.__stack[ref] if ref in self.__stack else None

    def __is_locked(self, value):
        for ref, item in self.__stack.items():
            if item['object']['oid'] == value or item['object']['dn'] == value:
                return True

        return False

    def __get_lock(self, value):
        for ref, item in self.__stack.items():
            if item['object']['oid'] == value or item['object']['dn'] == value:
                return item

        return None

    def __gc(self):
        self.env.log.debug("running garbage collector on object store")
        ten_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=10)
        e = EventMaker()
        command = PluginRegistry.getInstance("CommandRegistry")
        sched = PluginRegistry.getInstance("SchedulerService").getScheduler()

        for ref, item in list(self.__stack.items()):
            uuid = item['object']['uuid']
            if uuid is None:
                # new items without uuid do not need to be closed by timeout
                continue
            last_interaction_time = item['last_interaction'] if 'last_interaction' in item else item['created']
            if last_interaction_time < ten_minutes_ago:
                if 'mark_for_deletion' in item:
                    if item['mark_for_deletion'] <= datetime.datetime.now():
                        if 'countdown_job' in item:
                            try:
                                sched.unschedule_job(item['countdown_job'])
                            except KeyError:
                                pass
                            finally:
                                del item['countdown_job']

                        del self.__stack[ref]

                        event = e.Event(
                            e.ObjectCloseAnnouncement(
                                e.Target(item['user']),
                                e.SessionId(item['session_id']),
                                e.State("closed"),
                                e.UUID(uuid)
                            )
                        )
                        command.sendEvent(item['user'], event)
                else:
                    # notify user to do something otherwise the lock gets removed in 1 minute
                    event = e.Event(
                        e.ObjectCloseAnnouncement(
                            e.Target(item['user']),
                            e.SessionId(item['session_id']),
                            e.State("closing"),
                            e.UUID(uuid),
                            e.Minutes("1")
                        )
                    )
                    command.sendEvent(item['user'], event)
                    item['mark_for_deletion'] = datetime.datetime.now() + datetime.timedelta(seconds=59)
                    if 'countdown_job' in item:
                        try:
                            sched.unschedule_job(item['countdown_job'])
                        except KeyError:
                            pass
                        finally:
                            del item['countdown_job']

                    item['countdown_job'] = sched.add_date_job(self.__gc,
                                                               datetime.datetime.now() + datetime.timedelta(minutes=1),
                                                               tag="_internal",
                                                               jobstore="ram")

            elif 'mark_for_deletion' in item:
                # item has been modified -> remove the deletion mark
                del item['mark_for_deletion']
                event = e.Event(
                    e.ObjectCloseAnnouncement(
                        e.Target(item['user']),
                        e.SessionId(item['session_id']),
                        e.State("closing_aborted"),
                        e.UUID(uuid)
                    )
                )
                command.sendEvent(item['user'], event)
                if 'countdown_job' in item:
                    try:
                        sched.unschedule_job(item['countdown_job'])
                    except KeyError:
                        pass
                    finally:
                        del item['countdown_job']
