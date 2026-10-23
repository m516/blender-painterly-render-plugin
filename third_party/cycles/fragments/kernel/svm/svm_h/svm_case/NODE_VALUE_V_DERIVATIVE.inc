      SVM_CASE(NODE_VALUE_V_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_value_v<dual3>(stack, svm_node_get<SVMNodeValueV>(kg, &offset));
      }
      break;
