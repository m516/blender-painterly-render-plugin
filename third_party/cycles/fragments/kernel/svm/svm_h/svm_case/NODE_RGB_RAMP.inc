      SVM_CASE(NODE_RGB_RAMP)
      {
        const ccl_global auto &node = svm_node_get<SVMNodeRGBRamp>(kg, &offset);
        offset = svm_node_rgb_ramp(kg, stack, node, offset);
      }
      break;
