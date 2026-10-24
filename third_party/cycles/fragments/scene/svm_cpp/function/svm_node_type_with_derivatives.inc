static ShaderNodeType svm_node_type_with_derivatives(ShaderNodeType type)
{
  switch (type) {
#define SHADER_NODE_TYPE_DERIVATIVE(name) \
  case name: \
    return name##_DERIVATIVE;
#include "kernel/svm/node_types_template.h"

    default:
      break;
  }

  return type;
}
