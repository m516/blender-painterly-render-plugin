      SVM_CASE(NODE_CLOSURE_BACKGROUND)
      IF_KERNEL_NODES_FEATURE(EMISSION)
      {
        svm_node_closure_background(
            sd, stack, closure_weight, svm_node_get<SVMNodeClosureBackground>(kg, &offset));
      }
      break;
