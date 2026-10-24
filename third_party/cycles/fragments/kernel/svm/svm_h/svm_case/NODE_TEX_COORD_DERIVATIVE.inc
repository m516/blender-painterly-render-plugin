      SVM_CASE(NODE_TEX_COORD_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        const ccl_global auto &node = svm_node_get<SVMNodeTexCoord>(kg, &offset);
        offset = svm_node_tex_coord_derivative(kg, sd, path_visibility, stack, node, offset);
      }
      break;
