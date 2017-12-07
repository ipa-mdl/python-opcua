"""
Support for custom structures in client and server
We only support a subset of features but should be enough
for custom structures
"""

import os
import importlib
import re
import logging
# The next two imports are for generated code
from datetime import datetime
from enum import IntEnum
import uuid

from lxml import objectify


from opcua.ua.ua_binary import Primitives
from opcua import ua


def get_default_value(uatype):
    if uatype == "String":
        return "None"
    elif uatype == "Guid":
        return "uuid.uuid4()"
    elif uatype in ("ByteString", "CharArray", "Char"):
        return None
    elif uatype == "Boolean":
        return "True"
    elif uatype == "DateTime":
        return "datetime.utcnow()"
    elif uatype in ("Int16", "Int32", "Int64", "UInt16", "UInt32", "UInt64", "Double", "Float", "Byte", "SByte"):
        return 0
    else:
        return "ua.{0}() if not issubclass(ua.{0}, IntEnum) else ua.{0}(0)".format(uatype)


class Struct(object):
    def __init__(self, name):
        self.name = name
        self.fields = []
        self.typeid = None

    def get_code(self):
        code = """

class {0}(object):

    '''
    {0} structure autogenerated from xml
    '''

""".format(self.name)

        code += "    ua_types = [\n"
        for field in self.fields:
            prefix = "ListOf" if field.array else ""
            uatype = prefix + field.uatype
            if uatype == "ListOfChar":
                uatype = "String"
            code += "        ('{}', '{}'),\n".format(field.name, uatype)

        code += "    ]"
        code += """

    def __init__(self):
""".format(self.name)
        if not self.fields:
            code += "    pass"
        for field in self.fields:
            code += "        self.{} = {}\n".format(field.name, field.value)
        return code


class Field(object):
    def __init__(self, name):
        self.name = name
        self.uatype = None
        self.value = None
        self.array = False

class Enum(object):
    def __init__(self, name):
        self.name = name
        self.values = []

    def get_code(self):
        code = """

class {0}(IntEnum):

    '''
    {0} Enum autogenerated from xml
    '''
""".format(self.name)
        for value in self.values:
            code += "    {} = {}\n".format(*value)
        return code

class StructGenerator(object):
    def __init__(self):
        self.model = []

    def make_model_from_string(self, xml):
        obj = objectify.fromstring(xml)
        self._make_model(obj)

    def make_model_from_file(self, path):
        obj = objectify.parse(path)
        root = obj.getroot()
        self._make_model(root)

    def _make_model(self, root):
        for child in root.iter("{*}StructuredType"):
            struct = Struct(child.get("Name"))
            array = False
            for xmlfield in child.iter("{*}Field"):
                name = xmlfield.get("Name")
                if name.startswith("NoOf"):
                    array = True
                    continue
                field = Field(_clean_name(name))
                field.uatype = xmlfield.get("TypeName")
                if ":" in field.uatype:
                    field.uatype = field.uatype.split(":")[1]
                field.uatype = _clean_name(field.uatype)
                field.value = get_default_value(field.uatype)
                if array:
                    field.array = True
                    field.value = []
                    array = False
                struct.fields.append(field)
            self.model.append(struct)
        for child in root.iter("{*}EnumeratedType"):
            enum = Enum(child.get('Name'))
            for el in child.iter("{*}EnumeratedValue"):
                enum.values.append((_clean_name(el.get('Name')), el.get('Value')))
            self.model.append(enum)
    def save_to_file(self, path, register=False):
        _file = open(path, "wt")
        self._make_header(_file)
        for struct in self.model:
            _file.write(struct.get_code())
        if register:
            _file.write(self._make_registration())
        _file.close()

    def _make_registration(self):
        code = "\n\n"
        for struct in self.model:
            code += "ua.register_extension_object('{name}', ua.NodeId.from_string('{nodeid}'), {name})\n".format(name=struct.name, nodeid=struct.typeid)
        return code

    def get_python_classes(self, env=None):
        """
        generate Python code and execute in a new environment
        return a dict of structures {name: class}
        Rmw: Since the code is generated on the fly, in case of error the stack trace is
        not available and debugging is very hard...
        """
        if env is None:
            env = {}
        #  Add the required libraries to dict
        if "ua" not in env:
            env['ua'] = ua
        if "datetime" not in env:
            env['datetime'] = datetime
        if "IntEnum" not in env:
            env['IntEnum'] = IntEnum
        if "uuid" not in env:
            env['uuid'] = uuid
        # generate classes one by one and add them to dict
        res = {}
        for struct in self.model:
            code = struct.get_code()
            exec(code, env)
            res[struct.name] = env[struct.name]
        return res

    def save_and_import(self, path, append_to=None):
        """
        save the new structures to a python file which be used later
        import the result and return resulting classes in a dict
        if append_to is a dict, the classes are added to the dict
        """
        self.save_to_file(path)
        name = os.path.basename(path)
        name = os.path.splitext(name)[0]
        mymodule = importlib.import_module(name)
        if append_to is None:
            result = {}
        else:
            result = append_to
        for struct in self.model:
            result[struct.name] = getattr(mymodule, struct.name)
        return result

    def _make_header(self, _file):
        _file.write("""
'''
THIS FILE IS AUTOGENERATED, DO NOT EDIT!!!
'''

from datetime import datetime
from enum import IntEnum
import uuid

from opcua import ua
""")

    def set_typeid(self, name, typeid):
        for struct in self.model:
            if struct.name == name:
                struct.typeid = typeid
                return


def load_type_definitions(server, nodes=None):
    """
    Download xml from given variable node defining custom structures.
    If no node is given, attemps to import variables from all nodes under
    "0:OPC Binary"
    the code is generated and imported on the fly. If you know the structures
    are not going to be modified it might be interresting to copy the generated files
    and include them in you code
    """
    if nodes is None:
        nodes = []
        for desc in server.nodes.opc_binary.get_children_descriptions():
            if desc.BrowseName != ua.QualifiedName("Opc.Ua"):
                nodes.append(server.get_node(desc.NodeId))

    structs_dict = {}
    generators = []
    for node in nodes:
        xml = node.get_value()
        xml = xml.decode("utf-8")
        generator = StructGenerator()
        generators.append(generator)
        generator.make_model_from_string(xml)
        # generate and execute new code on the fly
        generator.get_python_classes(structs_dict)
        # same but using a file that is imported. This can be usefull for debugging library
        #name = node.get_browse_name().Name
        # Make sure structure names do not contain charaters that cannot be used in Python class file names
        #name = _clean_name(name)
        #name = "structures_" + node.get_browse_name().Name
        #generator.save_and_import(name + ".py", append_to=structs_dict)

        # register classes
        # every children of our node should represent a class
        names = set(structs_dict.keys())
        for ndesc in node.get_children_descriptions():
            ndesc_node = server.get_node(ndesc.NodeId)
            name = _clean_name(ndesc.BrowseName.Name)
            ref_desc_list = ndesc_node.get_references(refs=ua.ObjectIds.HasDescription, direction=ua.BrowseDirection.Inverse)
            if ref_desc_list:  #some server put extra things here
                if not name in structs_dict:
                    logging.getLogger(__name__).warning("Error {} is found as child of binary definition node but is not found in xml".format(name))
                    continue
                nodeid = ref_desc_list[0].NodeId
                ua.register_extension_object(name, nodeid, structs_dict[name])
                names.remove(name)
                # save the typeid if user want to create static file for type definitnion
                generator.set_typeid(name, nodeid.to_string())
        for name in names:
            ua.register_class_type_for_decoding(name, structs_dict[name])
    return generators, structs_dict


def _clean_name(name):
    """
    Remove characters that might be present in  OPC UA structures
    but cannot be part of of Python class names
    """
    name = re.sub(r'\W+', '_', name)
    name = re.sub(r'^[0-9]+', r'_\g<0>', name)

    return name
