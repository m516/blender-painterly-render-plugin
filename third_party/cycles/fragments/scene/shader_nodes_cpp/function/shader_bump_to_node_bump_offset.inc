static NodeBumpOffset shader_bump_to_node_bump_offset(ShaderBump bump)
{
  switch (bump) {
    case SHADER_BUMP_DX:
      return NODE_BUMP_OFFSET_DX;
    case SHADER_BUMP_DY:
      return NODE_BUMP_OFFSET_DY;
    default:
      return NODE_BUMP_OFFSET_CENTER;
  }
}
