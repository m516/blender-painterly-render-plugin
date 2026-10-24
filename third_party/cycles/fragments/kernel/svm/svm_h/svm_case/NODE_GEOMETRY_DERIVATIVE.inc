      SVM_CASE(NODE_GEOMETRY_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_geometry<dual3>(kg, sd, stack, svm_node_get<SVMNodeGeometry>(kg, &offset));
      }
      break;
