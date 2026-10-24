      SVM_CASE(NODE_GEOMETRY)
      svm_node_geometry<float3>(kg, sd, stack, svm_node_get<SVMNodeGeometry>(kg, &offset));
      break;
