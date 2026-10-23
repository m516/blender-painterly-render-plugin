      SVM_CASE(NODE_CONVERT)
      svm_node_convert<float, float3>(kg, stack, svm_node_get<SVMNodeConvert>(kg, &offset));
      break;
