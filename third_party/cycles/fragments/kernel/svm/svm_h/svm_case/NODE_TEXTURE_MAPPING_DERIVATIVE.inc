      SVM_CASE(NODE_TEXTURE_MAPPING_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_texture_mapping<dual3>(stack, svm_node_get<SVMNodeTextureMapping>(kg, &offset));
      }
      break;
