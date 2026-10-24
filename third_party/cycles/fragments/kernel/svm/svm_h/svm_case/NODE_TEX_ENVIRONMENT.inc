      SVM_CASE(NODE_TEX_ENVIRONMENT)
      svm_node_tex_environment<float3>(
          kg, sd, stack, svm_node_get<SVMNodeTexEnvironment>(kg, &offset));
      break;
