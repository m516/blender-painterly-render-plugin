      SVM_CASE(NODE_SEPARATE_VECTOR_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_separate_vector<dual3>(stack, svm_node_get<SVMNodeSeparateVector>(kg, &offset));
      }
      break;
