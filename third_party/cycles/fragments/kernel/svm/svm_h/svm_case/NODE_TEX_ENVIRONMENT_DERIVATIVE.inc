      SVM_CASE(NODE_TEX_ENVIRONMENT_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_tex_environment<dual3>(
            kg, sd, stack, svm_node_get<SVMNodeTexEnvironment>(kg, &offset));
      }
      break;
