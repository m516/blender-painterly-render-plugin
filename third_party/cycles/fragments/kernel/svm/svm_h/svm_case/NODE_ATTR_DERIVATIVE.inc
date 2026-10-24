      SVM_CASE(NODE_ATTR_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_attr_derivative(kg, sd, stack, svm_node_get<SVMNodeAttr>(kg, &offset));
      }
      break;
