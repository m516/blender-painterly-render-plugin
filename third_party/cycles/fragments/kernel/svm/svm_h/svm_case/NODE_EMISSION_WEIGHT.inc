      SVM_CASE(NODE_EMISSION_WEIGHT)
      IF_KERNEL_NODES_FEATURE(EMISSION)
      {
        svm_node_emission_weight(
            stack, &closure_weight, svm_node_get<SVMNodeEmissionWeight>(kg, &offset));
      }
      break;
