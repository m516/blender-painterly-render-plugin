      SVM_CASE(NODE_VALUE_F_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_value_f<dual1>(stack, svm_node_get<SVMNodeValueF>(kg, &offset));
      }
      break;
