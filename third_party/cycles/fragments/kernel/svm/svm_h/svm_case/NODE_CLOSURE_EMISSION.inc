      SVM_CASE(NODE_CLOSURE_EMISSION)
      IF_KERNEL_NODES_FEATURE(EMISSION)
      {
        svm_node_closure_emission(
            kg, sd, stack, closure_weight, svm_node_get<SVMNodeClosureEmission>(kg, &offset));
      }
      break;
