      SVM_CASE(NODE_TEX_IMAGE_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_tex_image<dual3>(kg, sd, stack, svm_node_get<SVMNodeTexImage>(kg, &offset));
      }
      break;
