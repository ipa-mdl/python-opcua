
import os.path

import opcua
from opcua import ua

from opcua.server.standard_address_space.standard_address_space_part3 import create_standard_address_space_Part3
from opcua.server.standard_address_space.standard_address_space_part4 import create_standard_address_space_Part4
from opcua.server.standard_address_space.standard_address_space_part5 import create_standard_address_space_Part5
from opcua.server.standard_address_space.standard_address_space_part8 import create_standard_address_space_Part8
from opcua.server.standard_address_space.standard_address_space_part9 import create_standard_address_space_Part9
from opcua.server.standard_address_space.standard_address_space_part10 import create_standard_address_space_Part10
from opcua.server.standard_address_space.standard_address_space_part11 import create_standard_address_space_Part11
from opcua.server.standard_address_space.standard_address_space_part13 import create_standard_address_space_Part13


def fill_address_space(nodeservice):
    node = ua.AddNodesItem()
    node.RequestedNewNodeId = ua.NodeId.from_string("i=78")
    node.BrowseName = ua.QualifiedName.from_string("Mandatory")
    node.NodeClass = ua.NodeClass.Object
    node.TypeDefinition = ua.NodeId.from_string("i=77")
    attrs = ua.ObjectAttributes()
    attrs.Description = ua.LocalizedText("Specifies that an instance with the attributes and references of the instance declaration must appear when a type is instantiated.")
    attrs.DisplayName = ua.LocalizedText("Mandatory")
    attrs.EventNotifier = 0
    node.NodeAttributes = attrs
    nodeservice.add_nodes([node])

    create_standard_address_space_Part3(nodeservice)
    create_standard_address_space_Part4(nodeservice)
    create_standard_address_space_Part5(nodeservice)
    create_standard_address_space_Part8(nodeservice)
    create_standard_address_space_Part9(nodeservice)
    create_standard_address_space_Part10(nodeservice)
    create_standard_address_space_Part11(nodeservice)
    create_standard_address_space_Part13(nodeservice)
