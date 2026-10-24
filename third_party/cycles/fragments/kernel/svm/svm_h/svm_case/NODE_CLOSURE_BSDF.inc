      SVM_CASE(NODE_CLOSURE_BSDF)
      {
        const ccl_global SVMNodeClosureBsdf &bsdf_node = svm_node_get<SVMNodeClosureBsdf>(kg,
                                                                                          &offset);
        offset = svm_node_closure_bsdf<node_feature_mask, type>(
            kg, sd, stack, closure_weight, bsdf_node, path_visibility, path_flag, offset);
      }
      break;
