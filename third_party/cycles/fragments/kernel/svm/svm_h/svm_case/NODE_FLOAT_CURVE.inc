      SVM_CASE(NODE_FLOAT_CURVE)
      {
        const ccl_global auto &node = svm_node_get<SVMNodeFloatCurve>(kg, &offset);
        offset = svm_node_curve(kg, stack, node, offset);
      }
      break;
