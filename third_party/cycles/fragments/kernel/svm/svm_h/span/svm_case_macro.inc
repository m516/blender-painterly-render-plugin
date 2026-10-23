#ifdef __KERNEL_USE_DATA_CONSTANTS__
#  define SVM_CASE(node) \
    case node: \
      if (!kernel_data_svm_usage_##node) \
        break;
#else
#  define SVM_CASE(node) case node:
#endif
