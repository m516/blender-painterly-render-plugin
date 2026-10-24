      SVM_CASE(NODE_TEX_COORD)
      {
        const ccl_global auto &node = svm_node_get<SVMNodeTexCoord>(kg, &offset);
        offset = svm_node_tex_coord(kg, sd, path_visibility, stack, node, offset);
      }
      break;
