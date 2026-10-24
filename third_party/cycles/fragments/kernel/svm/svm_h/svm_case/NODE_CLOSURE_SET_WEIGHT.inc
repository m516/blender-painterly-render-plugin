      SVM_CASE(NODE_CLOSURE_SET_WEIGHT)
      svm_node_closure_set_weight(&closure_weight,
                                  svm_node_get<SVMNodeClosureSetWeight>(kg, &offset));
      break;
