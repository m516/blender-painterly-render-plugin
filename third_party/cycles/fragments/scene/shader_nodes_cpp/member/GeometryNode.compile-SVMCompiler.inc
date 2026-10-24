void GeometryNode::compile(SVMCompiler &compiler)
{
  const NodeBumpOffset bump_offset = shader_bump_to_node_bump_offset(bump);
  const bool use_derivative = need_derivatives() || (bump != SHADER_BUMP_NONE);
  const uint8_t store_derivatives = need_derivatives();
  ShaderOutput *out;

  out = output("Position");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_GEOMETRY,
                      SVMNodeGeometry{
                          .geom_type = NODE_GEOM_P,
                          .bump_offset = bump_offset,
                          .store_derivatives = store_derivatives,
                          .out_offset = compiler.output("Position"),
                          .bump_filter_width = bump_filter_width,
                      },
                      use_derivative);
  }

  /* Currently no bump offset is supported for Normal, Tangent, True Normal, and Incoming. */
  out = output("Normal");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_GEOMETRY,
                      SVMNodeGeometry{
                          .geom_type = NODE_GEOM_N,
                          .bump_offset = NODE_BUMP_OFFSET_CENTER,
                          .store_derivatives = store_derivatives,
                          .out_offset = compiler.output("Normal"),
                          .bump_filter_width = bump_filter_width,
                      });
  }

  out = output("Tangent");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_GEOMETRY,
                      SVMNodeGeometry{
                          .geom_type = NODE_GEOM_T,
                          .bump_offset = NODE_BUMP_OFFSET_CENTER,
                          .store_derivatives = store_derivatives,
                          .out_offset = compiler.output("Tangent"),
                          .bump_filter_width = bump_filter_width,
                      },
                      use_derivative);
  }

  out = output("True Normal");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_GEOMETRY,
                      SVMNodeGeometry{
                          .geom_type = NODE_GEOM_Ng,
                          .bump_offset = NODE_BUMP_OFFSET_CENTER,
                          .store_derivatives = store_derivatives,
                          .out_offset = compiler.output("True Normal"),
                          .bump_filter_width = bump_filter_width,
                      },
                      use_derivative);
  }

  out = output("Incoming");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_GEOMETRY,
                      SVMNodeGeometry{
                          .geom_type = NODE_GEOM_I,
                          .bump_offset = NODE_BUMP_OFFSET_CENTER,
                          .store_derivatives = store_derivatives,
                          .out_offset = compiler.output("Incoming"),
                          .bump_filter_width = bump_filter_width,
                      },
                      use_derivative);
  }

  out = output("Parametric");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_GEOMETRY,
                      SVMNodeGeometry{
                          .geom_type = NODE_GEOM_uv,
                          .bump_offset = bump_offset,
                          .store_derivatives = store_derivatives,
                          .out_offset = compiler.output("Parametric"),
                          .bump_filter_width = bump_filter_width,
                      },
                      use_derivative);
  }

  out = output("Backfacing");
  if (!out->links.empty()) {
    compiler.add_node(this,
                      NODE_LIGHT_PATH,
                      SVMNodeLightPath{
                          .path_type = NODE_LP_backfacing,
                          .out_offset = compiler.output("Backfacing"),
                      });
  }

  out = output("Pointiness");
  if (!out->links.empty()) {
    if (compiler.output_type() != SHADER_TYPE_VOLUME) {
      compiler.add_node(this,
                        NODE_ATTR,
                        SVMNodeAttr{
                            .attr = int(ATTR_STD_POINTINESS),
                            .out_offset = compiler.output("Pointiness"),
                            .output_type = NODE_ATTR_OUTPUT_FLOAT,
                            .bump_offset = bump_offset,
                            .store_derivatives = store_derivatives,
                            .bump_filter_width = bump_filter_width,
                        },
                        use_derivative);
    }
    else {
      compiler.add_value_node(this, 0.0f, compiler.output("Pointiness"));
    }
  }

  out = output("Random Per Island");
  if (!out->links.empty()) {
    if (compiler.output_type() != SHADER_TYPE_VOLUME) {
      compiler.add_node(this,
                        NODE_ATTR,
                        SVMNodeAttr{
                            .attr = int(ATTR_STD_RANDOM_PER_ISLAND),
                            .out_offset = compiler.output("Random Per Island"),
                            .output_type = NODE_ATTR_OUTPUT_FLOAT,
                            .bump_offset = bump_offset,
                            .store_derivatives = store_derivatives,
                            .bump_filter_width = bump_filter_width,
                        },
                        use_derivative);
    }
    else {
      compiler.add_value_node(this, 0.0f, compiler.output("Random Per Island"));
    }
  }
}
