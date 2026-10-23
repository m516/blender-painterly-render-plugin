      SVM_CASE(NODE_COMBINE_VECTOR_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_combine_vector<dual3>(stack, svm_node_get<SVMNodeCombineVector>(kg, &offset));
      }
      break;
