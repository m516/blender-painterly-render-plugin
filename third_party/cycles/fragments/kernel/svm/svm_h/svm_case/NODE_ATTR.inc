      SVM_CASE(NODE_ATTR)
      IF_KERNEL_NODES_FEATURE(VOLUME)
      {
#ifdef __VOLUME__
        svm_node_attr_volume(kg, sd, stack, svm_node_get<SVMNodeAttr>(kg, &offset));
#endif
      }
      else {
        svm_node_attr_surface(kg, sd, stack, svm_node_get<SVMNodeAttr>(kg, &offset));
      }
      break;
