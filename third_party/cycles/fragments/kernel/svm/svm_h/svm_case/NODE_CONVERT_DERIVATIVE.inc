      SVM_CASE(NODE_CONVERT_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_convert<dual1, dual3>(kg, stack, svm_node_get<SVMNodeConvert>(kg, &offset));
      }
      break;
