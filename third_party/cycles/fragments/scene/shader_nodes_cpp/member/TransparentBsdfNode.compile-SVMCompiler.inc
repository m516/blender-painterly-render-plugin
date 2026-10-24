void TransparentBsdfNode::compile(SVMCompiler &compiler)
{
  BsdfNode::compile(compiler, SVMNodeSimpleBsdfData{});
}
