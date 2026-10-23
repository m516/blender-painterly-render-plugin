      SVM_CASE(NODE_MAPPING_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_mapping<dual3>(stack, svm_node_get<SVMNodeMapping>(kg, &offset));
      }
      break;
