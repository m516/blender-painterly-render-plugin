void TextureCoordinateNode::compile(SVMCompiler &compiler)
{
  const NodeBumpOffset bump_offset = shader_bump_to_node_bump_offset(bump);
  const bool use_derivative = need_derivatives() || (bump != SHADER_BUMP_NONE);
  const bool store_derivatives = need_derivatives();
  ShaderOutput *out;

  out = output("Generated");
  if (!out->links.empty()) {
    if (compiler.background) {
      compiler.add_node(this,
                        NODE_GEOMETRY,
                        SVMNodeGeometry{
                            .geom_type = NODE_GEOM_P,
                            .bump_offset = bump_offset,
                            .store_derivatives = store_derivatives,
                            .out_offset = compiler.output("Generated"),
                            .bump_filter_width = bump_filter_width,
                        },
                        use_derivative);
    }
    else {
      if (from_dupli) {
        /* Dupli generated coordinates are constant, no bump offset. */
        compiler.add_node(this,
                          NODE_TEX_COORD,
                          SVMNodeTexCoord{
                              .texco_type = NODE_TEXCO_DUPLI_GENERATED,
                              .bump_offset = NODE_BUMP_OFFSET_CENTER,
                              .store_derivatives = store_derivatives,
                              .out_offset = compiler.output("Generated"),
                              .bump_filter_width = bump_filter_width,
                          },
                          use_derivative);
      }
      else if (compiler.output_type() == SHADER_TYPE_VOLUME) {
        compiler.add_node(this,
                          NODE_TEX_COORD,
                          SVMNodeTexCoord{
                              .texco_type = NODE_TEXCO_VOLUME_GENERATED,
                              .bump_offset = bump_offset,
                              .store_derivatives = store_derivatives,
                              .out_offset = compiler.output("Generated"),
                              .bump_filter_width = bump_filter_width,
                          },
                          use_derivative);
      }
      else {
        compiler.add_node(this,
                          NODE_ATTR,
                          SVMNodeAttr{
                              .attr = int(compiler.attribute(ATTR_STD_GENERATED)),
                              .out_offset = compiler.output("Generated"),
                              .output_type = NODE_ATTR_OUTPUT_FLOAT3,
                              .bump_offset = bump_offset,
                              .store_derivatives = store_derivatives,
                              .bump_filter_width = bump_filter_width,
                          },
                          use_derivative);
      }
    }
  }

  out = output("Normal");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_TEX_COORD,
                      SVMNodeTexCoord{
                          .texco_type = NODE_TEXCO_NORMAL,
                          .bump_offset = bump_offset,
                          .store_derivatives = store_derivatives,
                          .out_offset = compiler.output("Normal"),
                          .bump_filter_width = bump_filter_width,
                      },
                      use_derivative);
  }

  out = output("UV");
  if (!out->links.empty()) {
    if (from_dupli) {
      /* Dupli UV coordinates aren't constant, no bump offset. */
      compiler.add_node(this,
                        NODE_TEX_COORD,
                        SVMNodeTexCoord{
                            .texco_type = NODE_TEXCO_DUPLI_UV,
                            .bump_offset = NODE_BUMP_OFFSET_CENTER,
                            .store_derivatives = store_derivatives,
                            .out_offset = compiler.output("UV"),
                            .bump_filter_width = bump_filter_width,
                        },
                        use_derivative);
    }
    else {
      compiler.add_node(this,
                        NODE_ATTR,
                        SVMNodeAttr{
                            .attr = int(compiler.attribute(ATTR_STD_UV)),
                            .out_offset = compiler.output("UV"),
                            .output_type = NODE_ATTR_OUTPUT_FLOAT3,
                            .bump_offset = bump_offset,
                            .store_derivatives = store_derivatives,
                            .bump_filter_width = bump_filter_width,
                        },
                        use_derivative);
    }
  }

  out = output("Object");
  if (!out->links.empty()) {
    compiler.add_node(
        this,
        NODE_TEX_COORD,
        SVMNodeTexCoord{
            .texco_type = (use_transform) ? NODE_TEXCO_OBJECT_WITH_TRANSFORM : NODE_TEXCO_OBJECT,
            .bump_offset = bump_offset,
            .store_derivatives = store_derivatives,
            .out_offset = compiler.output("Object"),
            .bump_filter_width = bump_filter_width,
        },
        use_derivative);
    if (use_transform) {
      const PackedTransform ob_itfm = transform_inverse(ob_tfm);
      compiler.add_node_data(ob_itfm);
    }
  }

  out = output("Camera");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_TEX_COORD,
                      SVMNodeTexCoord{
                          .texco_type = NODE_TEXCO_CAMERA,
                          .bump_offset = bump_offset,
                          .store_derivatives = store_derivatives,
                          .out_offset = compiler.output("Camera"),
                          .bump_filter_width = bump_filter_width,
                      },
                      use_derivative);
  }

  out = output("Window");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_TEX_COORD,
                      SVMNodeTexCoord{
                          .texco_type = NODE_TEXCO_WINDOW,
                          .bump_offset = bump_offset,
                          .store_derivatives = store_derivatives,
                          .out_offset = compiler.output("Window"),
                          .bump_filter_width = bump_filter_width,
                      },
                      use_derivative);
  }

  /* Reflection currently does not support bump offset. */
  out = output("Reflection");
  if (!out->links.empty()) {
    if (compiler.background) {
      compiler.add_node(this,
                        NODE_GEOMETRY,
                        SVMNodeGeometry{
                            .geom_type = NODE_GEOM_I,
                            .bump_offset = NODE_BUMP_OFFSET_CENTER,
                            .store_derivatives = store_derivatives,
                            .out_offset = compiler.output("Reflection"),
                            .bump_filter_width = bump_filter_width,
                        },
                        use_derivative);
    }
    else {
      compiler.add_node(this,
                        NODE_TEX_COORD,
                        SVMNodeTexCoord{
                            .texco_type = NODE_TEXCO_REFLECTION,
                            .bump_offset = NODE_BUMP_OFFSET_CENTER,
                            .store_derivatives = store_derivatives,
                            .out_offset = compiler.output("Reflection"),
                            .bump_filter_width = bump_filter_width,
                        },
                        use_derivative);
    }
  }
}
