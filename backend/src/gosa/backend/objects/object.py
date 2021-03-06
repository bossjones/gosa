# This file is part of the GOsa framework.
#
#  http://gosa-project.org
#
# Copyright:
#  (C) 2016 GONICUS GmbH, Germany, http://www.gonicus.de
#
# See the LICENSE file in the project's top-level directory for details.

"""
The object base class.
"""

import copy
import zope.event
import pkg_resources
import os
from lxml import etree
from lxml.builder import E
from logging import getLogger
from zope.interface import Interface, implementer
from gosa.common import Environment
from gosa.common.utils import N_, is_uuid
from gosa.common.components import PluginRegistry
from gosa.common.error import GosaErrorHandler as C
from gosa.backend.objects.backend.registry import ObjectBackendRegistry
from gosa.backend.exceptions import ObjectException


# Status
STATUS_OK = 0
STATUS_CHANGED = 1


# Register the errors handled  by us
C.register_codes(dict(
    CREATE_NEEDS_BASE=N_("Creation of '%(location)s' lacks a base DN"),
    READ_BACKEND_PROPERTIES=N_("Error reading properties for backend '%(backend)s'"),
    ATTRIBUTE_BLOCKED_BY=N_("Attribute is blocked by %(source)s==%(value)s"),
    ATTRIBUTE_READ_ONLY=N_("Attribute '%(topic)s' is read only"),
    ATTRIBUTE_MANDATORY=N_("Attribute '%(topic)s' is mandatory"),
    ATTRIBUTE_INVALID_CONSTANT=N_("Value is invalid - expected one of %(elements)s"),
    ATTRIBUTE_INVALID_LIST=N_("Value is invalid - expected a list"),
    ATTRIBUTE_INVALID=N_("Value is invalid - expected value of type '%(type)s'"),
    ATTRIBUTE_CHECK_FAILED=N_("Value is invalid"),
    ATTRIBUTE_NOT_UNIQUE=N_("Value is not unique (%(value)s)"),
    ATTRIBUTE_NOT_FOUND=N_("Attribute not found"),
    OBJECT_MODE_NOT_AVAILABLE=N_("Mode '%(mode)s' is not available for base objects"),
    OBJECT_MODE_BASE_AVAILABLE=N_("Mode '%(mode)s' is only available for base objects"),
    OBJECT_NOT_SUB_FOR=N_("Object of type '%(ext)s' cannot be added as to the '%(base)s' container"),
    OBJECT_REMOVE_NON_BASE_OBJECT=N_("Cannot remove non base object"),
    OBJECT_MOVE_NON_BASE_OBJECT=N_("Cannot move non base object"),
    OBJECT_BASE_NO_RETRACT=N_("Base object cannot be retracted"),
    FILTER_INVALID_KEY=N_("Invalid key '%(key)s' for filter '%(filter)s'"),
    FILTER_MISSING_KEY=N_("Missing key '%(key)s' after processing filter '%(filter)s'"),
    FILTER_NO_LIST=N_("Filter '%(filter)s' did not return a %(type)s value - a list was expected"),
    ATTRIBUTE_DEPEND_LOOP=N_("Potential loop in attribute dependencies")
))


class Object(object):
    """
    This class is the base class for all objects.

    It contains getter and setter methods for the object
    attributes and it is able to initialize itself by reading data from
    backends.

    It also contains the ability to execute the in- and out-filters for the
    object properties.

    All meta-classes for objects, created by the XML definitions, will inherit this class.

    """
    _reg = None
    _backend = None
    _mode = False
    _propsByBackend = {}
    uuid = None
    dn = None
    orig_dn = None
    log = None
    createTimestamp = None
    modifyTimestamp = None
    myProperties = None
    env = None
    parent = None
    _owner = None
    _session_id = None
    attributesInSaveOrder = None

    def __saveOrder(self):
        """
        Returns a list containing all attributes in the correct
        save-order.
        Due to the fact that some attributes depend on another,
        we have to save some attributes first and then the others.
        """

        data = self.__saveOrderHelper()
        attrs = []
        for level in sorted(data.keys(), reverse=True):
            for attr in data[level]:
                if attr not in attrs:
                    attrs.append(attr)
        return attrs

    def __saveOrderHelper(self, res=None, item=None, level=0):
        """
        Helper method for '__saveOrder' to detect the dependency
        depth (level) for an attribute
        """

        if not res:
            res = {}

        if not level in res:
            res[level] = []

        if level == 10:
            raise ValueError(C.make_error('ATTRIBUTE_DEPEND_LOOP'))

        if not item:
            for key in self.myProperties:
                self.__saveOrderHelper(res, key, level + 1)
        else:
            if len(self.myProperties[item]['depends_on']):
                for key in self.myProperties[item]['depends_on']:
                    self.__saveOrderHelper(res, key, level + 1)

            res[level].append(item)
        return res

    def __init__(self, where=None, mode="update"):
        self.env = Environment.getInstance()

        # Instantiate Backend-Registry
        self._reg = ObjectBackendRegistry.getInstance()
        self.log = getLogger(__name__)
        self.log.debug("new object instantiated '%s'" % type(self).__name__)

        # Group attributes by Backend
        propsByBackend = {}
        props = getattr(self, '__properties')

        self.myProperties = copy.deepcopy(props)
        self.attributesInSaveOrder = self.__saveOrder()

        atypes = self._objectFactory.getAttributeTypes()
        for key in self.myProperties:

            # Load dynamic dropdown-values
            if self.myProperties[key]['values_populate']:
                cr = PluginRegistry.getInstance('CommandRegistry')
                values = cr.call(self.myProperties[key]['values_populate'])
                if type(values).__name__ == "dict":
                    self.myProperties[key]['values'] = values
                else:
                    self.myProperties[key]['values'] = atypes['String'].convert_to(self.myProperties[key]['type'], values)

            # Initialize an empty array for each backend
            for be in self.myProperties[key]['backend']:
                if be not in propsByBackend:
                    propsByBackend[be] = []

                # Append property
                propsByBackend[be].append(key)

        self._propsByBackend = propsByBackend
        self._mode = mode

        # Initialize object using a DN
        if where:
            if mode == "create":
                if is_uuid(where):
                    raise ValueError(C.make_error('CREATE_NEEDS_BASE', "base", location=where))
                self.orig_dn = self.dn = where

            else:
                self._read(where)

        # Set status to modified for attributes that do not have a value but are
        # mandatory and have a default.
        # This ensures that default values are passed to the out_filters and get saved
        # afterwards.
        # (Defaults will be passed to in-filters too, if they are not overwritten by _read())
        for key in self.myProperties:
            if not(self.myProperties[key]['value']) and self.myProperties[key]['default'] is not None and \
                len(self.myProperties[key]['default']):
                self.myProperties[key]['value'] = copy.deepcopy(self.myProperties[key]['default'])
                if self.myProperties[key]['mandatory']:
                    self.myProperties[key]['status'] = STATUS_CHANGED

    def set_foreign_value(self, attr, original):
        self.myProperties[attr]['value'] = original['value']
        self.myProperties[attr]['in_value'] = original['in_value']
        self.myProperties[attr]['orig_value'] = original['orig_value']

    def listProperties(self):
        return self.myProperties.keys()

    def getProperties(self):
        return copy.deepcopy(self.myProperties)

    def listMethods(self):
        methods = getattr(self, '__methods')
        return methods.keys()

    def hasattr(self, attr):
        return attr in self.myProperties

    def _read(self, where):
        """
        This method tries to initialize a object instance by reading data
        from the defined backend.

        Attributes will be grouped by their backend to ensure that only one
        request per backend will be performed.

        """
        # Generate missing values
        if is_uuid(where):
            #pylint: disable=E1101
            if self._base_object:
                self.dn = self._reg.uuid2dn(self._backend, where)
            else:
                self.dn = None

            self.uuid = where
        else:
            self.dn = where
            self.uuid = self._reg.dn2uuid(self._backend, where)

        # Get last change timestamp
        self.orig_dn = self.dn
        if self.dn:
            self.createTimestamp, self.modifyTimestamp = self._reg.get_timestamps(self._backend, self.dn)

        # Load attributes for each backend.
        # And then assign the values to the properties.
        self.log.debug("object uuid: %s" % self.uuid)

        for backend in self._propsByBackend:

            try:
                # Create a dictionary with all attributes we want to fetch
                # {attribute_name: type, name: type}
                info = dict([(k, self.myProperties[k]['backend_type']) for k in self._propsByBackend[backend]])
                self.log.debug("loading attributes for backend '%s': %s" % (backend, str(info)))
                be = ObjectBackendRegistry.getBackend(backend)
                be_attrs = self._backendAttrs[backend] if backend in self._backendAttrs else None
                attrs = be.load(self.uuid, info, be_attrs)

            except ValueError as e:
                raise ObjectException(C.make_error('READ_BACKEND_PROPERTIES', backend=backend))

            # Assign fetched value to the properties.
            for key in self._propsByBackend[backend]:

                if key not in attrs:
                    self.log.debug("attribute '%s' was not returned by load" % key)
                    continue

                # Keep original values, they may be overwritten in the in-filters.
                self.myProperties[key]['in_value'] = self.myProperties[key]['value'] = attrs[key]
                self.log.debug("%s: %s" % (key, self.myProperties[key]['value']))

        # Once we've loaded all properties from the backend, execute the
        # in-filters.
        for key in self.myProperties:

            # Skip loading in-filters for None values
            if self.myProperties[key]['value'] is None:
                self.myProperties[key]['in_value'] = self.myProperties[key]['value'] = []
                continue

            # Execute defined in-filters.
            if len(self.myProperties[key]['in_filter']):
                self.log.debug("found %s in-filter(s)  for attribute '%s'" % (str(len(self.myProperties[key]['in_filter'])), key))

                # Execute each in-filter
                for in_f in self.myProperties[key]['in_filter']:
                    self.__processFilter(in_f, key, self.myProperties)

        # Convert the received type into the target type if not done already
        #pylint: disable=E1101
        atypes = self._objectFactory.getAttributeTypes()
        for key in self.myProperties:

            # Convert values from incoming backend-type to required type
            if self.myProperties[key]['value']:
                a_type = self.myProperties[key]['type']
                be_type = self.myProperties[key]['backend_type']

                #  Convert all values to required type
                if not atypes[a_type].is_valid_value(self.myProperties[key]['value']):
                    try:
                        self.myProperties[key]['value'] = atypes[a_type].convert_from(be_type, self.myProperties[key]['value'])
                    except Exception as e:
                        self.log.error("conversion of '%s' from '%s' to type '%s' failed: %s" % (key, be_type, a_type, str(e)))
                    else:
                        self.log.debug("converted '%s' from type '%s' to type '%s'!" % (key, be_type, a_type))

            # Keep the initial value
            self.myProperties[key]['last_value'] = self.myProperties[key]['orig_value'] = copy.deepcopy(self.myProperties[key]['value'])

    def _delattr_(self, name):
        """
        Deleter method for properties.
        """
        if name in self.attributesInSaveOrder:

            # Check if this attribute is blocked by another attribute and its value.
            for bb in self.myProperties[name]['blocked_by']:
                if bb['value'] in self.myProperties[bb['name']]['value']:
                    raise AttributeError(C.make_error(
                        'ATTRIBUTE_BLOCKED_BY', name,
                        source=bb['name'], value=bb['value']))

            # Do not allow to write to read-only attributes.
            if self.myProperties[name]['readonly']:
                raise AttributeError(C.make_error('ATTRIBUTE_READ_ONLY', name))

            # Do not allow remove mandatory attributes
            if self.myProperties[name]['mandatory']:
                raise AttributeError(C.make_error('ATTRIBUTE_MANDATORY', name))

            # If not already in removed state
            if len(self.myProperties[name]['value']) != 0:
                self.myProperties[name]['status'] = STATUS_CHANGED
                self.myProperties[name]['last_value'] = copy.deepcopy(self.myProperties[name]['value'])
                self.myProperties[name]['value'] = []
        else:
            raise AttributeError(C.make_error('ATTRIBUTE_NOT_FOUND', name))

    def _setattr_(self, name, value):
        """
        This is the setter method for object attributes.
        Each given attribute value is validated with the given set of
        validators.
        """

        # Store non property values
        try:
            object.__getattribute__(self, name)
            self.__dict__[name] = value
            return
        except AttributeError:
            pass

        # A none value was passed to clear the value
        if value is None:
            self._delattr_(name)
            return

        # Try to save as property value
        if name in self.myProperties:

            # Check if this attribute is blocked by another attribute and its value.
            for bb in  self.myProperties[name]['blocked_by']:
                if bb['value'] in self.myProperties[bb['name']]['value']:
                    raise AttributeError(C.make_error(
                        'ATTRIBUTE_BLOCKED_BY', name,
                        source=bb['name'], value=bb['value']))

            # Do not allow to write to read-only attributes.
            if self.myProperties[name]['readonly']:
                raise AttributeError(C.make_error('ATTRIBUTE_READ_ONLY', name))

            # Set the new value
            if self.myProperties[name]['multivalue']:

                # Check if the new value is s list.
                if type(value) != list:
                    raise TypeError(C.make_error('ATTRIBUTE_INVALID_LIST', name))
                new_value = value
            else:
                new_value = [value]

            # Eventually fixup value from incoming JSON string
            s_type = self.myProperties[name]['type']
            try:
                new_value = self._objectFactory.getAttributeTypes()[s_type].fixup(new_value)
            except Exception:
                raise TypeError(C.make_error('ATTRIBUTE_INVALID', name, type=s_type))

            # Check if the new value is valid
            #pylint: disable=E1101
            if not self._objectFactory.getAttributeTypes()[s_type].is_valid_value(new_value):
                raise TypeError(C.make_error('ATTRIBUTE_INVALID', name, type=s_type))

            # Check if the given value has to match one out of a given list.
            if len(self.myProperties[name]['values']) and [True for x in new_value if x not in self.myProperties[name]['values']]:
                raise TypeError(C.make_error(
                    'ATTRIBUTE_INVALID_CONSTANT', name,
                    elements=", ".join(self.myProperties[name]['values'])))

            # Validate value
            if self.myProperties[name]['validator']:

                props_copy = copy.deepcopy(self.myProperties)

                res, error = self.__processValidator(self.myProperties[name]['validator'], name, new_value, props_copy)
                if not res:
                    if len(error):
                        # TODO: check if we really want the validators to manipulate the data?
                        # remove invalid values from value list
                        error_indexes = [err["index"] for err in error if "index" in err]
                        error_indexes.sort(reverse=True)
                        for index in error_indexes:
                            del new_value[index]

                        if not len(new_value):
                            # nothing left to save
                            raise ValueError(C.make_error('ATTRIBUTE_CHECK_FAILED', name, details=error))
                        else:
                            res, error = self.__processValidator(self.myProperties[name]['validator'], name, new_value, props_copy)
                            if not res:
                                if len(error):
                                    raise ValueError(C.make_error('ATTRIBUTE_CHECK_FAILED', name, details=error))
                                else:
                                    raise ValueError(C.make_error('ATTRIBUTE_CHECK_FAILED', name))
                    else:
                        raise ValueError(C.make_error('ATTRIBUTE_CHECK_FAILED', name))

            # Ensure that unique values stay unique. Let the backend test this.
            #if self.myProperties[name]['unique']:
            #    backendI = ObjectBackendRegistry.getBackend(self.myProperties[name]['backend'])
            #    if not backendI.is_uniq(name, new_value):
            #        raise ObjectException(C.make_error('ATTRIBUTE_NOT_UNIQUE', name, value=value))

            current = copy.deepcopy(self.myProperties[name]['value'])

            # Assign the properties new value.
            self.myProperties[name]['value'] = new_value
            self.log.debug("updated property value of [%s|%s] %s:%s" % (type(self).__name__, self.uuid, name, new_value))

            # Update status if there's a change
            t = self.myProperties[name]['type']

            #pylint: disable=E1101
            if not self._objectFactory.getAttributeTypes()[t].values_match(self.myProperties[name]['value'], self.myProperties[name]['orig_value']):
                self.myProperties[name]['status'] = STATUS_CHANGED
                self.myProperties[name]['last_value'] = current

        else:
            raise AttributeError(C.make_error('ATTRIBUTE_NOT_FOUND', name))

    def _getattr_(self, name):
        """
        The getter method object attributes.

        (It differentiates between object attributes and class-members)
        """
        methods = getattr(self, '__methods')

        # If the requested property exists in the object-attributes, then return it.
        if name in self.myProperties:

            # We can have single and multivalues, return the correct type here.
            value = None
            if self.myProperties[name]['multivalue']:
                value = self.myProperties[name]['value']
            else:
                if len(self.myProperties[name]['value']):
                    value = self.myProperties[name]['value'][0]
            return value

        # The requested property-name seems to be a method, return the method reference.
        elif name in methods:

            def m_call(*args, **kwargs):
                return methods[name]['ref'](self, *args, **kwargs)
            return m_call

        else:
            raise AttributeError(C.make_error('ATTRIBUTE_NOT_FOUND', name))

    def getTemplate(self):
        """
        Return the template data - if any. Else None.
        """
        return Object.getNamedTemplate(self.env, self._templates)

    @staticmethod
    def getNamedTemplate(env, templates):
        """
        Return the template data - if any. Else None.
        """
        ui = []

        # If there's a template file, try to find it
        if templates:
            for template in templates:
                path = None

                # Absolute path
                if template.startswith(os.path.sep):
                    path = template

                # Relative path
                else:
                    # Find path
                    path = pkg_resources.resource_filename('gosa.backend', os.path.join('data', 'templates', template)) #@UndefinedVariable
                    if not os.path.exists(path):
                        path = os.path.join(env.config.getBaseDir(), 'templates', template)
                        if not os.path.exists(path):
                            return None

                with open(path, "rb") as f:
                    ui.append(f.read().decode('utf-8'))

        return ui

    def getAttrType(self, name):
        """
        Return the type of a given object attribute.
        """

        if name in self.myProperties:
            return self.myProperties[name]['type']

        raise AttributeError(C.make_error('ATTRIBUTE_NOT_FOUND', name))

    def check(self, propsFromOtherExtensions=None):
        """
        Checks whether everything is fine with the extension and its given values or not.
        """
        if not propsFromOtherExtensions:
            propsFromOtherExtensions = {}

        # Create a copy to avoid touching the original values
        props = copy.deepcopy(self.myProperties)

        # Check if _mode matches with the current object type
        #pylint: disable=E1101
        if self._base_object and not self._mode in ['create', 'remove', 'update']:
            raise ObjectException(C.make_error('OBJECT_MODE_NOT_AVAILABLE', mode=self._mode))
        if not self._base_object and self._mode in ['create', 'remove']:
            raise ObjectException(C.make_error('OBJECT_MODE_BASE_AVAILABLE', mode=self._mode))

        # Check if we are allowed to create this base object on the given base
        if self._base_object and self._mode == "create":
            base_type = self.get_object_type_by_dn(self.dn)
            if not base_type:
                raise ObjectException(C.make_error('OBJECT_MODE_BASE_AVAILABLE', mode=self._mode))

            if self.__class__.__name__ not in self._objectFactory.getAllowedSubElementsForObject(base_type, includeInvisible=True):
                raise ObjectException(C.make_error('OBJECT_NOT_SUB_FOR',
                    ext=self.__class__.__name__,
                    base=base_type))

        # Transfer values form other commit processes into ourselfes
        for key in self.attributesInSaveOrder:
            if props[key]['foreign'] and key in propsFromOtherExtensions:
                props[key]['value'] = propsFromOtherExtensions[key]['value']

            # Transfer status into commit status
            props[key]['commit_status'] = props[key]['status']

        # Collect values by store and process the property filters
        for key in self.attributesInSaveOrder:

            # Skip foreign properties
            if props[key]['foreign']:
                continue

            # Check if this attribute is blocked by another attribute and its value.
            is_blocked = False
            for bb in props[key]['blocked_by']:
                if bb['value'] in props[bb['name']]['value']:
                    is_blocked = True
                    break

            # Check if all required attributes are set. (Skip blocked once, they cannot be set!)
            if not is_blocked and props[key]['mandatory'] and not len(props[key]['value']):
                raise ObjectException(C.make_error('ATTRIBUTE_MANDATORY', key))

            # Process each and every out-filter with a clean set of input values,
            #  to avoid that return-values overwrite themselves.
            if len(props[key]['out_filter']):

                self.log.debug(" found %s out-filter for %s" % (str(len(props[key]['out_filter'])), key,))
                for out_f in props[key]['out_filter']:
                    self.__processFilter(out_f, key, props)

        return props

    def commit(self, propsFromOtherExtensions=None):
        """
        Commits changes of an object to the corresponding backends.
        """
        if not propsFromOtherExtensions:
            propsFromOtherExtensions = {}

        self.check(propsFromOtherExtensions)

        self.log.debug("saving object modifications for [%s|%s]" % (type(self).__name__, self.uuid))

        # Create a copy to avoid touching the original values
        props = copy.deepcopy(self.myProperties)

        # Transfer status into commit status
        for key in self.attributesInSaveOrder:
            props[key]['commit_status'] = props[key]['status']

            # Transfer values form other commit processes into ourselfes
            if props[key]['foreign'] and key in propsFromOtherExtensions:
                props[key]['value'] = propsFromOtherExtensions[key]['value']

        # Adapt property states
        # Run this once - If any state was adapted, then run again to ensure
        # that all dependencies are processed.
        first = True
        _max = 5
        required = False
        while (first or required) and _max:
            first = False
            required = False
            _max -= 1
            for key in self.attributesInSaveOrder:

                # Adapt status from dependent properties.
                for propname in props[key]['depends_on']:
                    old = props[key]['commit_status']
                    props[key]['commit_status'] |= props[propname]['status'] & STATUS_CHANGED
                    props[key]['commit_status'] |= props[propname]['commit_status'] & STATUS_CHANGED
                    if props[key]['commit_status'] != old:
                        required = True

        # Collect values by store and process the property filters
        collectedAttrs = {}
        for key in self.attributesInSaveOrder:

            # Skip foreign properties
            if props[key]['foreign']:
                continue

            # Do not save untouched values
            if not props[key]['commit_status'] & STATUS_CHANGED:
                continue

            # Get the new value for the property and execute the out-filter
            self.log.debug("changed: %s" % (key,))

            # Process each and every out-filter with a clean set of input values,
            #  to avoid that return-values overwrite themselves.
            if len(props[key]['out_filter']):

                self.log.debug(" found %s out-filter for %s" % (str(len(props[key]['out_filter'])), key,))
                for out_f in props[key]['out_filter']:
                    self.__processFilter(out_f, key, props)

        # Collect properties by backend
        for prop_key in self.attributesInSaveOrder:

            # Skip foreign properties
            if props[prop_key]['foreign']:
                continue

            # Do not save untouched values
            if not props[prop_key]['commit_status'] & STATUS_CHANGED:
                continue

            collectedAttrs[prop_key] = props[prop_key]

        # Create a backend compatible list of all changed attributes.
        toStore = {}
        for prop_key in collectedAttrs:

            # Collect properties by backend
            for be in props[prop_key]['backend']:

                if not be in toStore:
                    toStore[be] = {}

                # Convert the properities type to the required format - if its not of the expected type.
                be_type = collectedAttrs[prop_key]['backend_type']
                s_type = collectedAttrs[prop_key]['type']

                if not self._objectFactory.getAttributeTypes()[be_type].is_valid_value(collectedAttrs[prop_key]['value']):
                    collectedAttrs[prop_key]['value'] = self._objectFactory.getAttributeTypes()[s_type].convert_to(
                            be_type, collectedAttrs[prop_key]['value'])

                # Append entry to the to-be-stored list
                toStore[be][prop_key] = {'foreign': collectedAttrs[prop_key]['foreign'],
                                    'orig': collectedAttrs[prop_key]['in_value'],
                                    'value': collectedAttrs[prop_key]['value'],
                                    'type': collectedAttrs[prop_key]['backend_type']}

        # We may have a plugin without any attributes, like the group asterisk extension, in
        # this case we've to update the object despite of the lack of properties.
        if not len(toStore) and self._backend:
            toStore[self._backend] = {}

        # Leave the show if there's nothing to do
        tmp = {}
        for key, value in toStore.items():

            # Skip NULL backend. Nothing to save, anyway.
            if key == "NULL":
                continue

            tmp[key] = value

        toStore = tmp

        # Skip the whole process if there's no change at all
        if not toStore:
            return {}

        # Update references using the toStore information
        changes = {}
        for be in toStore:
            changes.update(toStore[be])

        self.update_refs(changes)

        # Handle by backend
        p_backend = getattr(self, '_backend')
        obj = self

        zope.event.notify(ObjectChanged("pre %s" % self._mode, obj))

        # Call pre-hooks now
        if self._mode in ["extend", "create"]:
            self.__execute_hook("PreCreate")

        if self._mode in ["update"]:
            self.__execute_hook("PreModify")

        # First, take care about the primary backend...
        if p_backend in toStore:
            beAttrs = self._backendAttrs[p_backend] if p_backend in self._backendAttrs else {}
            be = ObjectBackendRegistry.getBackend(p_backend)
            if self._mode == "create":
                obj.uuid = be.create(self.dn, toStore[p_backend], self._backendAttrs[p_backend])

            elif self._mode == "extend":
                be.extend(self.uuid, toStore[p_backend],
                        self._backendAttrs[p_backend],
                        self.getForeignProperties())

            else:
                be.update(self.uuid, toStore[p_backend], beAttrs)

            # Eventually the DN has changed
            if self._base_object:
                dn = be.uuid2dn(self.uuid)

                # Take DN for newly created objects
                if self._mode == "create":
                    if self._base_object:
                        obj.dn = dn

                elif dn != obj.dn:

                    self.update_dn_refs(dn)

                    obj.dn = dn
                    if self._base_object:
                        zope.event.notify(ObjectChanged("post move", obj))

                    obj.orig_dn = dn

        # ... then walk thru the remaining ones
        for backend, data in toStore.items():

            # Skip primary backend - already done
            if backend == p_backend:
                continue

            be = ObjectBackendRegistry.getBackend(backend)
            beAttrs = self._backendAttrs[backend] if backend in self._backendAttrs else {}
            if self._mode == "create":
                be.create(self.dn, data, beAttrs)
            elif self._mode == "extend":
                be.extend(self.uuid, data, beAttrs, self.getForeignProperties())
            else:
                be.update(self.uuid, data, beAttrs)

        zope.event.notify(ObjectChanged("post %s" % self._mode, obj))

        # Call post-hooks now
        if self._mode in ["extend", "create"]:
            self.__execute_hook("PostCreate")
        if self._mode in ["update"] and "PostModify":
            self.__execute_hook("PostModify")

        return props

    def revert(self):
        """
        Reverts all changes made to this object since it was loaded.
        """
        for key in self.myProperties:
            self.myProperties[key]['value'] = self.myProperties[key]['last_value']

        self.log.debug("reverted object modifications for [%s|%s]" % (type(self).__name__, self.uuid))

    def getExclusiveProperties(self):
        return [x for x, y in self.myProperties.items() if not y['foreign']]

    def getForeignProperties(self):
        return [x for x, y in self.myProperties.items() if y['foreign']]

    def __processValidator(self, fltr, key, value, props_copy):
        """
        This method processes a given process-list (fltr) for a given property (prop).
        And return TRUE if the value matches the validator set and FALSE if
        not.
        """

        # This is our process-line pointer it points to the process-list line
        #  we're executing at the moment
        lptr = 0

        # Our filter result stack
        stack = list()
        self.log.debug(" validator started (%s)" % key)
        self.log.debug("  value: %s" % (value, ))

        # Process the list till we reach the end..
        lasterrmsg = ""
        errormsgs = []
        while (lptr + 1) in fltr:

            # Get the current line and increase the process list pointer.
            lptr += 1
            curline = fltr[lptr]

            # A condition matches for something and returns a boolean value.
            # We'll put this value on the stack for later use.
            if 'condition' in curline:

                # Build up argument list
                args = [props_copy, key, value] + curline['params']

                # Process condition and keep results
                fname = type(curline['condition']).__name__
                v, errors = (curline['condition']).process(*args)

                # Log what happend!
                self.log.debug("  %s: [Filter]  %s(%s) called and returned: %s" % (
                    lptr, fname, ", ".join(["\"" + x + "\"" for x in curline['params']]), v))

                # Append the result to the stack.
                stack.append(v)
                if not v:
                    if len(errors):
                        lasterrmsg = errors.pop()

            # A comparator compares two values from the stack and then returns a single
            #  boolean value.
            elif 'operator' in curline:
                v1 = stack.pop()
                v2 = stack.pop()
                fname = type(curline['operator']).__name__
                res = (curline['operator']).process(v1, v2)
                stack.append(res)

                # Add last error message
                if not res:
                    errormsgs.append(lasterrmsg)
                    lasterrmsg = ""

                # Log what happend!
                self.log.debug("  %s: [OPERATOR]  %s(%s, %s) called and returned: %s" % (
                    lptr, fname, v1, v2, res))

        # Attach last error message
        res = stack.pop()
        if not res and lasterrmsg != "":
            errormsgs.append(lasterrmsg)

        self.log.debug(" <- VALIDATOR ENDED (%s)" % key)
        return res, errormsgs

    def __processFilter(self, fltr, key, prop):
        """
        This method processes a given process-list (fltr) for a given property (prop).
        For example: When a property has to be stored in the backend, it will
         run through the out-filter-process-list and thus will be transformed into a storable
         key, value pair.
        """

        # Search for replaceable patterns in the process-list.
        fltr = self.__fillInPlaceholders(fltr, prop)

        # This is our process-line pointer it points to the process-list line
        #  we're executing at the moment
        lptr = 0

        # Our filter result stack
        stack = list()

        # Log values
        self.log.debug(" -> FILTER STARTED (%s)" % key)

        # Process the list till we reach the end..
        while (lptr + 1) in fltr:

            # Get the current line and increase the process list pointer.
            lptr += 1
            curline = fltr[lptr]

            # A filter is used to manipulate the 'value' or the 'key' or maybe both.
            if 'filter' in curline:

                # Build up argument list
                args = [self, key, prop]
                fname = type(curline['filter']).__name__
                for entry in curline['params']:
                    args.append(entry)

                # Process filter and keep results
                key, prop = (curline['filter']).process(*args)

                # Ensure that the processed data is still valid.
                # Filter may mess things up and then the next cannot process correctly.
                if key not in prop:
                    raise ObjectException(C.make_error('FILTER_INVALID_KEY',
                        key=key, filter=fname))

                # Check if the filter returned all expected property values.
                for pk in prop:
                    if not all(k in prop[pk] for k in ('backend', 'value', 'type')):
                        missing = ", ".join({'backend', 'value', 'type'} - set(prop[pk].keys()))
                        raise ObjectException(C.make_error('FILTER_MISSING_KEY', key=missing, filter=fname))

                    # Check if the returned value-type is list or None.
                    if type(prop[pk]['value']) not in [list, type(None)]:
                        raise ObjectException(C.make_error('FILTER_NO_LIST',
                            key=pk, filter=fname, type=type(prop[pk]['value'])))

                self.log.debug("  %s: [Filter]  %s(%s) called " % (lptr, fname,
                    ", ".join(["\"" + x + "\"" for x in curline['params']])))

            # A condition matches for something and returns a boolean value.
            # We'll put this value on the stack for later use.
            elif 'condition' in curline:

                # Build up argument list
                args = [key] + curline['params']

                # Process condition and keep results
                stack.append((curline['condition']).process(*args))

                fname = type(curline['condition']).__name__
                self.log.debug("  %s: [Condition] %s(%s) called " % (lptr, fname, ", ".join(curline['params'])))

            # Handle jump, for example if a condition has failed, jump over its filter-chain.
            elif 'jump' in curline:

                # Jump to <line> -1 because we will increase the line ptr later.
                olptr = lptr
                if curline['jump'] == 'conditional':
                    if stack.pop():
                        lptr = curline['onTrue'] - 1
                    else:
                        lptr = curline['onFalse'] - 1
                else:
                    lptr = curline['to'] - 1

                self.log.debug("  %s: [Goto] %s ()" % (olptr, lptr))

            # A comparator compares two values from the stack and then returns a single
            #  boolean value.
            elif 'operator' in curline:
                a = stack.pop()
                b = stack.pop()
                stack.append((curline['operator']).process(a, b))

                fname = type(curline['operator']).__name__
                self.log.debug("  %s: [Condition] %s(%s, %s) called " % (lptr, fname, a, b))

            # Log current values
            #self.log.debug("  result")
            #for pkey in prop:
            #    self.log.debug("   %s: %s" % (pkey, prop[pkey]['value']))

        self.log.debug(" <- FILTER ENDED")
        return prop

    def __fillInPlaceholders(self, fltr, props):
        """
        This method fill in placeholder into in- and out-filters.
        """

        # Collect all property values
        propList = {}
        for key in props:
            if props[key]['multivalue']:
                propList[key] = props[key]['value']
            else:
                if props[key]['value'] and len(props[key]['value']):
                    propList[key] = props[key]['value'][0]
                else:
                    propList[key] = None

        # An inline function which replaces format string tokens
        def _placeHolder(x):
            try:
                x = x % propList
            except KeyError:
                pass

            return x

        # Walk trough each line of the process list an replace placeholders.
        for line in fltr:
            if 'params' in fltr[line]:
                fltr[line]['params'] = map(_placeHolder,
                        fltr[line]['params'])
        return fltr

    def get_object_type_by_dn(self, dn):
        """
        Returns the objectType for a given DN
        """
        index = PluginRegistry.getInstance("ObjectIndex")
        res = index.search({'dn': dn}, {'_type': 1})
        return res[0]['_type'] if len(res) == 1 else None

    def get_references(self, override=None):
        res = []
        index = PluginRegistry.getInstance("ObjectIndex")

        for ref, info in self._objectFactory.getReferences(override or self.__class__.__name__).items():

            for ref_attribute, dsc in info.items():
                for idsc in dsc:
                    if self.myProperties[idsc[1]]['orig_value'] and len(self.myProperties[idsc[1]]['orig_value']):
                        oval = self.myProperties[idsc[1]]['orig_value'][0]
                    else:
                        oval = None
                    dns = index.search({'_type': ref, ref_attribute: str(oval)}, {'dn': 1})
                    if len(dns):
                        dns = [x['dn'] for x in dns]
                    res.append((
                        ref_attribute,
                        idsc[1],
                        getattr(self, idsc[1]),
                        dns or [],
                        self.myProperties[idsc[1]]['multivalue']))

        return res

    def update_refs(self, data):
        for ref_attr, self_attr, value, refs, multivalue in self.get_references(): #@UnusedVariable

            for ref in refs:

                # Next iteration if there's no change for the relevant
                # attribute
                if not self_attr in data:
                    continue

                # Load object and change value to the new one
                c_obj = ObjectProxy(ref)
                c_value = getattr(c_obj, ref_attr)
                o_value = data[self_attr]['orig']

                if type(c_value) == list:
                    if type(o_value) == list:
                        c_value = list(filter(lambda x: x not in o_value, c_value))
                    else:
                        c_value = list(filter(lambda x: x != o_value, c_value))

                    if multivalue:
                        c_value.extend(data[self_attr]['value'])
                    else:
                        c_value.append(data[self_attr]['value'][0])

                    setattr(c_obj, ref_attr, list(set(c_value)))

                else:
                    setattr(c_obj, ref_attr, data[self_attr]['value'][0])

                c_obj.commit()

    def remove_refs(self):
        for ref_attr, self_attr, value, refs, multivalue in self.get_references(): #@UnusedVariable

            for ref in refs:
                c_obj = ObjectProxy(ref)
                c_value = getattr(c_obj, ref_attr)

                if type(c_value) == list:
                    if type(value) == list:
                        c_value = list(filter(lambda x: x not in value, c_value))
                    else:
                        c_value = list(filter(lambda x: x != value, c_value))

                    setattr(c_obj, ref_attr, c_value)

                else:
                    setattr(c_obj, ref_attr, None)

                c_obj.commit()

    def get_dn_references(self):
        res = []
        index = PluginRegistry.getInstance("ObjectIndex")

        for info in self._objectFactory.getReferences("*", "dn").values():
            for ref_attribute in info.keys():
                dns = index.search({ref_attribute: self.dn}, {'dn': 1})
                if len(dns):
                    dns = [x['dn'] for x in dns]
                res.append((ref_attribute,dns))

        return res

    def update_dn_refs(self, new_dn):
        for ref_attr, refs in self.get_dn_references():
            for ref in refs:
                c_obj = ObjectProxy(ref)
                c_value = getattr(c_obj, ref_attr)

                if type(c_value) == list:
                    c_value = list(filter(lambda x: x != self.dn, c_value))
                    c_value.append(new_dn)
                    setattr(c_obj, ref_attr, list(set(c_value)))

                else:
                    setattr(c_obj, ref_attr, new_dn)

                c_obj.commit()

    def remove_dn_refs(self):
        for ref_attr, refs in self.get_dn_references():
            for ref in refs:
                c_obj = ObjectProxy(ref)
                c_value = getattr(c_obj, ref_attr)

                if type(c_value) == list:
                    c_value = filter(lambda x: x != self.dn, c_value)
                    setattr(c_obj, ref_attr, list(set(c_value)))

                else:
                    setattr(c_obj, ref_attr, None)

                c_obj.commit()

    def remove(self):
        """
        Removes this object - and eventually it's containements.
        """
        #pylint: disable=E1101
        if not self._base_object:
            raise ObjectException(C.make_error('OBJECT_REMOVE_NON_BASE_OBJECT'))

        # Remove all references to ourselves
        self.remove_refs()

        # Collect backends
        backends = [getattr(self, '_backend')]
        be_attrs = {getattr(self, '_backend'): {}}

        for prop, info in self.myProperties.items():
            for backend in info['backend']:
                if not backend in backends:
                    backends.append(backend)

                if not backend in be_attrs:
                    be_attrs[backend] = {}

                if self.is_attr_set(prop):
                    be_attrs[backend][prop] = {'foreign': info['foreign'],
                                               'orig': info['in_value'],
                                               'value': info['value'],
                                               'type': info['backend_type']}

        # Remove for all backends, removing the primary one as the last one
        backends.reverse()
        obj = self
        zope.event.notify(ObjectChanged("pre remove", obj))

        # Call pre-remove now
        self.__execute_hook("PreRemove")

        for backend in backends:
            be = ObjectBackendRegistry.getBackend(backend)
            r_attrs = self.getExclusiveProperties()

            # Remove all non exclusive properties
            remove_attrs = {}
            for attr in be_attrs[backend]:
                if attr in r_attrs:
                    remove_attrs[attr] = be_attrs[backend][attr]

            self.remove_refs()
            self.remove_dn_refs()

            #pylint: disable=E1101
            be.remove(self.uuid, remove_attrs, self._backendAttrs[backend] \
                    if backend in self._backendAttrs else None)

        zope.event.notify(ObjectChanged("post remove", obj))

        # Call post-remove now
        self.__execute_hook("PostRemove")

    def simulate_move(self, orig_dn):
        """
        Simulate a moves for this object
        """
        #pylint: disable=E1101
        if not self._base_object:
            raise ObjectException(C.make_error('OBJECT_MOVE_NON_BASE_OBJECT'))

        obj = self
        zope.event.notify(ObjectChanged("pre move", obj, dn=self.dn, orig_dn=orig_dn))

        # Update the DN refs which have most probably changed
        self.update_dn_refs(self.dn)

        zope.event.notify(ObjectChanged("post move", obj, dn=self.dn, orig_dn=orig_dn))

    def move(self, new_base):
        """
        Moves this object - and eventually it's containements.
        """
        #pylint: disable=E1101
        if not self._base_object:
            raise ObjectException(C.make_error('OBJECT_MOVE_NON_BASE_OBJECT'))

        # Collect backends
        backends = [getattr(self, '_backend')]

        # Collect all other backends
        for info in self.myProperties.values():
            for be in info['backend']:
                if not be in backends:
                    backends.append(be)

        obj = self
        zope.event.notify(ObjectChanged("pre move", obj))

        # Move for primary backend
        be = ObjectBackendRegistry.getBackend(backends[0])
        be.move(self.uuid, new_base)

        # Update the DN refs which have most probably changed
        p_backend = getattr(self, '_backend')
        be = ObjectBackendRegistry.getBackend(p_backend)
        dn = be.uuid2dn(self.uuid)
        self.dn = dn
        self.update_dn_refs(dn)

        zope.event.notify(ObjectChanged("post move", obj, dn=dn))

    def retract(self):
        """
        Removes this object extension
        """
        #pylint: disable=E1101
        if self._base_object:
            raise ObjectException(C.make_error('OBJECT_BASE_NO_RETRACT'))

        # Call pre-remove now
        self.__execute_hook("PreRemove")

        # Remove all references to ourselves
        self.remove_refs()

        # Collect backends
        backends = [getattr(self, '_backend')]
        be_attrs = {getattr(self, '_backend'): {}}

        for prop, info in self.myProperties.items():
            for backend in info['backend']:
                if not backend in backends:
                    backends.append(backend)

                if not backend in be_attrs:
                    be_attrs[backend] = {}

                if self.is_attr_set(prop):
                    be_attrs[backend][prop] = {'foreign': info['foreign'],
                                               'orig': info['in_value'],
                                               'value': info['value'],
                                               'type': info['backend_type']}

        # Retract for all backends, removing the primary one as the last one
        backends.reverse()
        obj = self

        zope.event.notify(ObjectChanged("pre retract", obj))

        for backend in backends:
            be = ObjectBackendRegistry.getBackend(backend)
            r_attrs = self.getExclusiveProperties()

            # Remove all non exclusive properties
            remove_attrs = {}
            for attr in be_attrs[backend]:
                if attr in r_attrs:
                    remove_attrs[attr] = be_attrs[backend][attr]

            self.remove_refs()
            self.remove_dn_refs()

            #pylint: disable=E1101
            be.retract(self.uuid, remove_attrs, self._backendAttrs[backend] \
                    if backend in self._backendAttrs else None)

        zope.event.notify(ObjectChanged("post retract", obj))

        # Call post-remove now
        self.__execute_hook("PostRemove")

    def is_attr_set(self, name):
        return len(self.myProperties[name]['in_value']) > 0

    def is_attr_using_default(self, name):
        return not self.is_attr_set(name) and self.myProperties[name]['default'] == self.myProperties[name]['value']

    def __execute_hook(self, hook_type):

        # Call post-remove now
        hooks = getattr(self, '__hooks')
        if hook_type in hooks:
            for hook in hooks[hook_type]:
                hook["ref"](self)


class IObjectChanged(Interface):  # pragma: nocover

    def __init__(self, obj):
        pass


class IAttributeChanged(Interface):  # pragma: nocover

    def __init__(self, attr, value):
        pass

@implementer(IObjectChanged)
class ObjectChanged(object):

    def __init__(self, reason, obj=None, dn=None, uuid=None, orig_dn=None, o_type=None):
        self.reason = reason
        self.uuid = uuid or obj.uuid
        self.dn = dn or obj.dn
        self.orig_dn = orig_dn or obj.orig_dn
        self.o_type = o_type or obj.__class__.__name__

@implementer(IAttributeChanged)
class AttributeChanged(object):

    def __init__(self, reason, obj, target):
        self.reason = reason
        self.target = target
        self.uuid = obj.uuid


from gosa.backend.objects.proxy import ObjectProxy
