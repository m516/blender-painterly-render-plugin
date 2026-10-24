/* Shim: replaces Cycles scene/shader.cpp without devices, OSL or OCIO */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: the ShaderManager constructor computes only rgb_to_y and
 * the thin-film table. get_attribute_id() (both overloads) and linear_rgb_to_gray() are
 * byte-for-byte copies of scene/shader.cpp:483-502 and 894-897, and compute_thin_film_table()
 * and ensure_bsdf_table_impl() of scene/shader.cpp:932-993 and 1025-1036. Shader::set_graph() is
 * scene/shader.cpp:283-312 without the displacement hash (lines 290-293 and 296-305);
 * device_update_lookup_tables() and device_free_lookup_tables() hold scene/shader.cpp:714-729
 * and 752-757 verbatim. */

#include "scene/shader.h"
#include "scene/scene.h"
#include "scene/shader_graph.h"
#include "scene/shader_nodes.h"
#include "scene/tables.h"

#include "util/transform.h"

/* The BSDF lookup tables and the thin-film color matching functions, as upstream includes them
 * (scene/shader.cpp:28). The file opens its own CCL_NAMESPACE_BEGIN. */
#include "scene/shader.tables"

CCL_NAMESPACE_BEGIN

/* Shader */

Shader::~Shader() = default;

/* scene/shader.cpp:283-312 without lines 290-293 and 296-305 (the displacement hash). */
void Shader::set_graph(unique_ptr<ShaderGraph> &&graph_)
{
  /* do this here already so that we can detect if mesh or object attributes
   * are needed, since the node attribute callbacks check if their sockets
   * are connected but proxy nodes should not count */
  if (graph_) {
    graph_->remove_proxy_nodes();
  }

  /* assign graph */
  graph = std::move(graph_);

  /* Store info here before graph optimization to make sure that
   * nodes that get optimized away still count. */
  has_volume_connected = (graph->output()->input("Volume")->link != nullptr);
}

/* Shader Manager */

ShaderManager::ShaderManager() : thin_film_table_offset_(TABLE_OFFSET_INVALID)
{
  /* Upstream's constructor calls init_xyz_transforms() (scene/shader.cpp:455-460, 995-1023).
   * Built without OCIO, ColorSpaceManager::get_xyz_to_scene_linear_rgb() returns
   * get_xyz_to_rec709() (util/colorspace.cpp:739, 792), the matrix below
   * (util/colorspace.cpp:687-703). This shim keeps only rgb_to_y, the Y row of its inverse
   * (scene/shader.cpp:1018-1019), and the thin-film table (scene/shader.cpp:1022). */
  const Transform xyz_to_rgb = make_transform(3.2404542f,
                                              -1.5371385f,
                                              -0.4985314f,
                                              0.0f,
                                              -0.9692660f,
                                              1.8760108f,
                                              0.0415560f,
                                              0.0f,
                                              0.0556434f,
                                              -0.2040259f,
                                              1.0572252f,
                                              0.0f);
  const Transform rgb_to_xyz = transform_inverse(xyz_to_rgb);
  rgb_to_y = make_float3(rgb_to_xyz.y);

  compute_thin_film_table(xyz_to_rgb);
}

ShaderManager::~ShaderManager() = default;

uint64_t ShaderManager::get_attribute_id(ustring name)
{
  const thread_scoped_spin_lock lock(attribute_lock_);

  /* get a unique id for each name, for SVM attribute lookup */
  const AttributeIDMap::iterator it = unique_attribute_id.find(name);

  if (it != unique_attribute_id.end()) {
    return it->second;
  }

  const uint64_t id = ATTR_STD_NUM + unique_attribute_id.size();
  unique_attribute_id[name] = id;
  return id;
}

uint64_t ShaderManager::get_attribute_id(AttributeStandard std)
{
  return (uint64_t)std;
}

float ShaderManager::linear_rgb_to_gray(const float3 c)
{
  return dot(c, rgb_to_y);
}

/* ShaderManager::compute_thin_film_table: scene/shader.cpp:932-993, verbatim. */

void ShaderManager::compute_thin_film_table(const Transform &xyz_to_rgb)
{
  /* Our implementation of Thin Film Fresnel is based on
   * "A Practical Extension to Microfacet Theory for the Modeling of Varying Iridescence"
   * by Laurent Belcour and Pascal Barla
   * (https://belcour.github.io/blog/research/publication/2017/05/01/brdf-thin-film.html).
   *
   * The idea there is that for a naive implementation of Thin Film interference, you'd compute
   * the reflectivity for a given wavelength using Airy summation, and then numerically integrate
   * the product of this reflectivity function and the Color Matching Functions of the colorspace
   * you're working in to obtain the RGB (or XYZ) values.
   * However, this integration would require too many evaluations to be practical.
   * Therefore, they reformulate the computation as a rapidly converging series involving the
   * Fourier transform of the CMFs.
   *
   * Specifically, we need to:
   * - Compute the RGB CMFs from the XYZ CMFs using the working color space's XYZ-to-RGB matrix
   * - Resample the RGB CMFs to be parametrized by frequency instead of wavelength as usual
   * - Compute the FFT of the CMFs
   * - Store the result as a LUT
   * - Look up the values for each channel at runtime based on the optical path difference and
   *   phase shift.
   *
   * Computing an FFT here would be annoying, so we'd like to precompute it, but we only know
   * the XYZ-to-RGB matrix at runtime. Luckily, both resampling and FFT are linear operations,
   * so we can precompute the FFT of the resampled XYZ CMFs and then multiply each entry with
   * the XYZ-to-RGB matrix to get the RGB LUT.
   *
   * That's what this function does: We load the precomputed values, convert to RGB, normalize
   * the result to make the DC term equal to 1, and then store that into the final table that's
   * used by the kernel.
   */
  assert(sizeof(table_thin_film_cmf) == 6 * THIN_FILM_TABLE_SIZE * sizeof(float));
  thin_film_table.resize(6 * THIN_FILM_TABLE_SIZE);

  float3 normalization;
  for (int i = 0; i < THIN_FILM_TABLE_SIZE; i++) {
    const float *table_row = table_thin_film_cmf[i];
    /* Load precomputed resampled Fourier-transformed XYZ CMFs. */
    const float3 xyzReal = make_float3(table_row[0], table_row[1], table_row[2]);
    const float3 xyzImag = make_float3(table_row[3], table_row[4], table_row[5]);

    /* Linearly combine precomputed data to produce the RGB equivalents. Works since both
     * resampling and Fourier transformation are linear operations. */
    const float3 rgbReal = transform_direction(&xyz_to_rgb, xyzReal);
    const float3 rgbImag = transform_direction(&xyz_to_rgb, xyzImag);

    /* We normalize all entries by the first element. Since that is the DC component, it normalizes
     * the CMF (in non-Fourier space) to an area of 1. */
    if (i == 0) {
      normalization = 1.0f / rgbReal;
    }

    /* Store in lookup table. */
    thin_film_table[i + 0 * THIN_FILM_TABLE_SIZE] = rgbReal.x * normalization.x;
    thin_film_table[i + 1 * THIN_FILM_TABLE_SIZE] = rgbReal.y * normalization.y;
    thin_film_table[i + 2 * THIN_FILM_TABLE_SIZE] = rgbReal.z * normalization.z;
    thin_film_table[i + 3 * THIN_FILM_TABLE_SIZE] = rgbImag.x * normalization.x;
    thin_film_table[i + 4 * THIN_FILM_TABLE_SIZE] = rgbImag.y * normalization.y;
    thin_film_table[i + 5 * THIN_FILM_TABLE_SIZE] = rgbImag.z * normalization.z;
  }
}

/* ShaderManager::ensure_bsdf_table_impl: scene/shader.cpp:1025-1036, verbatim. */

size_t ShaderManager::ensure_bsdf_table_impl(DeviceScene *dscene,
                                             Scene *scene,
                                             const float *table,
                                             const size_t n)
{
  /* Since the BSDF tables are static arrays, we can use their address to identify them. */
  if (!(bsdf_tables.count(table))) {
    vector<float> entries(table, table + n);
    bsdf_tables[table] = scene->lookup_tables->add_table(dscene, entries);
  }
  return bsdf_tables[table];
}

/* Card T6.7: the body is scene/shader.cpp:714-729 of ShaderManager::device_update_common,
 * verbatim. */
void ShaderManager::device_update_lookup_tables(DeviceScene *dscene, Scene *scene)
{
  /* lookup tables */
  KernelTables *ktables = &dscene->data.tables;
  ktables->ggx_E = ensure_bsdf_table(dscene, scene, table_ggx_E);
  ktables->ggx_Eavg = ensure_bsdf_table(dscene, scene, table_ggx_Eavg);
  ktables->ggx_glass_E = ensure_bsdf_table(dscene, scene, table_ggx_glass_E);
  ktables->ggx_glass_Eavg = ensure_bsdf_table(dscene, scene, table_ggx_glass_Eavg);
  ktables->ggx_glass_inv_E = ensure_bsdf_table(dscene, scene, table_ggx_glass_inv_E);
  ktables->ggx_glass_inv_Eavg = ensure_bsdf_table(dscene, scene, table_ggx_glass_inv_Eavg);
  ktables->sheen_ltc = ensure_bsdf_table(dscene, scene, table_sheen_ltc);
  ktables->ggx_gen_schlick_ior_s = ensure_bsdf_table(dscene, scene, table_ggx_gen_schlick_ior_s);
  ktables->ggx_gen_schlick_s = ensure_bsdf_table(dscene, scene, table_ggx_gen_schlick_s);

  if (thin_film_table_offset_ == TABLE_OFFSET_INVALID) {
    thin_film_table_offset_ = scene->lookup_tables->add_table(dscene, thin_film_table);
  }
  dscene->data.tables.thin_film_table = (int)thin_film_table_offset_;
}

/* Card T6.7: the body is scene/shader.cpp:752-757 of ShaderManager::device_free_common,
 * verbatim. */
void ShaderManager::device_free_lookup_tables(Scene *scene)
{
  for (auto &entry : bsdf_tables) {
    scene->lookup_tables->remove_table(&entry.second);
  }
  bsdf_tables.clear();
  scene->lookup_tables->remove_table(&thin_film_table_offset_);
  thin_film_table_offset_ = TABLE_OFFSET_INVALID;
}

CCL_NAMESPACE_END
