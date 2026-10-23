      SVM_CASE(NODE_CURVES)
      {
        const ccl_global auto &node = svm_node_get<SVMNodeCurves>(kg, &offset);
        offset = svm_node_curves(kg, stack, node, offset);
      }
      break;
