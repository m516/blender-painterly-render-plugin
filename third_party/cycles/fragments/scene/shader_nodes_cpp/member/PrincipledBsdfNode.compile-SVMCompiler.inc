void PrincipledBsdfNode::compile(SVMCompiler &compiler)
{
  SVMStackOffset tangent_offset = SVM_STACK_INVALID;
  if (has_nonzero_weight("Anisotropic")) {
    tangent_offset = compiler.input_link("Tangent");
  }

  compiler.add_bsdf_node(
      SVMNodeClosureBsdf{
          .closure_type = closure,
          .mix_weight_offset = compiler.closure_mix_weight_offset(),
      },
      SVMNodePrincipledBsdfData{
          .distribution = distribution,
          .ior = compiler.input_float("IOR"),
          .roughness = compiler.input_float("Roughness"),
          /* Weights. */
          .sheen_weight = compiler.input_float("Sheen Weight"),
          .coat_weight = compiler.input_float("Coat Weight"),
          .metallic = compiler.input_float("Metallic"),
          .transmission_weight = compiler.input_float("Transmission Weight"),
          .subsurface_weight = compiler.input_float("Subsurface Weight"),
          /* Base. */
          .base_color = compiler.input_float3("Base Color"),
          .alpha = compiler.input_float("Alpha"),
          .diffuse_roughness = compiler.input_float("Diffuse Roughness"),
          /* Normals and tangents. */
          .normal_offset = compiler.input_link("Normal"),
          .tangent_offset = tangent_offset,
          .coat_normal_offset = compiler.input_link("Coat Normal"),
          /* Specular. */
          .specular_tint = compiler.input_float3("Specular Tint"),
          .specular_ior_level = compiler.input_float("Specular IOR Level"),
          .anisotropic = compiler.input_float("Anisotropic"),
          .anisotropic_rotation = compiler.input_float("Anisotropic Rotation"),
          /* Emission. */
          .emission_color = compiler.input_float3("Emission Color"),
          .emission_strength = compiler.input_float("Emission Strength"),
          /* Sheen. */
          .sheen_tint = compiler.input_float3("Sheen Tint"),
          .sheen_roughness = compiler.input_float("Sheen Roughness"),
          /* Coat. */
          .coat_tint = compiler.input_float3("Coat Tint"),
          .coat_roughness = compiler.input_float("Coat Roughness"),
          .coat_ior = compiler.input_float("Coat IOR"),
          /* Subsurface. */
          .subsurface_method = subsurface_method,
          .subsurface_radius = compiler.input_float3("Subsurface Radius"),
          .subsurface_scale = compiler.input_float("Subsurface Scale"),
          .subsurface_ior = compiler.input_float("Subsurface IOR"),
          .subsurface_anisotropy = compiler.input_float("Subsurface Anisotropy"),
          /* Thin film. */
          .thin_film_thickness = compiler.input_float("Thin Film Thickness"),
          .thin_film_ior = compiler.input_float("Thin Film IOR"),
          /* Thin wall. */
          .thin_wall = compiler.input_int("Thin Wall"),
      });
}
