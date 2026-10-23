      SVM_CASE(NODE_VECTOR_MATH_DERIVATIVE)
      IF_NOT_KERNEL_NODES_FEATURE(VOLUME)
      {
        svm_node_vector_math<dual3>(stack, svm_node_get<SVMNodeVectorMath>(kg, &offset));
      }
      break;
