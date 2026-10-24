/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Cycles' closure SVM nodes, the BSDF lookup tables and the painterly closure collector (card
 * T6.7). Each shader graph is built with cycles_scene, compiled and packed by
 * PainterlyShaderManager (card T6.5), evaluated by the generated svm_eval_nodes() and collected
 * by painterly_svm_collect() (painterly/kernel/svm/collect.h).
 *
 * Every expected value is exact:
 * - closure weights are products of dyadic inputs, which float32 represents exactly;
 * - the collector multiplies two floats in double, which is exact;
 * - the one value that depends on a lookup table (the diffuse weight of a Principled BSDF) is
 *   recomputed from the raw scene/shader.tables entries by repeating the upstream operations in
 *   the same order, in float32 (reference_lookup_corner()). */

#include "cycles_svm_test_support.h"

#include "cycles/shader_node_registry.h"
#include "painterly/kernel/svm/collect.h"
#include "painterly/scene/svm/shader_manager.h"

#include "graph/node_type.h"
#include "scene/scene.h"
#include "scene/shader.h"
#include "scene/shader_graph.h"
#include "scene/shader_nodes.h"

#include "util/array.h"
#include "util/progress.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include <doctest/doctest.h>

/* The raw tables, to compare with the uploaded ones. The file opens its own CCL_NAMESPACE. */
#include "scene/shader.tables"

CCL_NAMESPACE_BEGIN

namespace {

/* A Scene whose shader_manager is a PainterlyShaderManager (card T6.5). */
unique_ptr<Scene> make_scene()
{
  painterly_cycles_shader_node_types();
  unique_ptr<Scene> scene = make_unique<Scene>();
  scene->shader_manager = make_unique<PainterlyShaderManager>();
  return scene;
}

PainterlyShaderManager &shader_manager(Scene &scene)
{
  return static_cast<PainterlyShaderManager &>(*scene.shader_manager);
}

/* Creates a node from its Cycles type name (card T6.4, "Socket naming"). */
ShaderNode *create_node_by_name(ShaderGraph &graph, const char *type_name)
{
  const NodeType *type = NodeType::find(ustring(type_name));
  REQUIRE(type != nullptr);
  return graph.create_node(type);
}

/* Sets a parameter (a socket without a ShaderInput) by member name and enum name (card T6.4,
 * "Socket naming"). */
void set_enum(ShaderNode *node, const char *member_name, const char *enum_name)
{
  const SocketType *socket = node->type->find_input(ustring(member_name));
  REQUIRE(socket != nullptr);
  node->set(*socket, ustring(enum_name));
}

/* Adds a referenced shader with `graph` to the scene. */
Shader *add_shader(Scene &scene, unique_ptr<ShaderGraph> &&graph)
{
  unique_ptr<Shader> shader = make_unique<Shader>();
  shader->set_graph(std::move(graph));
  shader->reference();
  scene.shaders.push_back(std::move(shader));
  return scene.shaders[scene.shaders.size() - 1];
}

/* Compiles every shader of `scene` as Cycles' device update does: ShaderGraph::finalize with
 * constant folding, then SVMCompiler and packing (card T6.5), then the lookup tables (card T6.7).
 */
void compile(Scene &scene)
{
  Progress progress;
  shader_manager(scene).device_update_pre(nullptr, &scene.dscene, &scene, progress);
  shader_manager(scene).device_update_post(nullptr, &scene.dscene, &scene, progress);
  shader_manager(scene).device_update_lookup_tables(&scene.dscene, &scene);
}

/* Links output `output` of `closure` to the Surface of `graph`'s output node, and adds the graph
 * as a shader of `scene`. */
Shader *add_surface(Scene &scene,
                    unique_ptr<ShaderGraph> &&graph,
                    ShaderNode *closure,
                    const char *output)
{
  graph->connect(closure->output(output), graph->output()->input("Surface"));
  return add_shader(scene, std::move(graph));
}

/* The result of one evaluation. `sd` is the ShaderData that svm_eval_nodes() wrote; the
 * collector read it in place (painterly/kernel/svm/collect.h, "Contract"). */
struct Evaluation {
  ShaderData sd;
  PainterlySvmTrace trace;
  PainterlySvmMaterial material;
};

/* Evaluates shader `shader_id` of `scene` as surface_shader_eval() calls svm_eval_nodes()
 * (kernel/integrator/surface_shader.h:1248-1297), at a hit seen head-on: N = Ng = wi = +Z, so
 * that every cosine is 1. sd->flag comes from the shader's KernelShader, as
 * shader_setup_from_ray() sets it (kernel/geom/shader_data.h:113). Then collects. */
template<uint node_feature_mask = painterly_svm_surface_feature_mask>
void evaluate(const Scene &scene, const int shader_id, Evaluation &out)
{
  KernelGlobalsCPU globals;
  PainterlyShaderManager::bind_kernel_globals(scene.dscene, globals);
  out.sd = painterly_svm_test_shader_data(shader_id);
  out.sd.flag = scene.dscene.shaders[shader_id].flags;
  out.sd.N = make_float3(0.0f, 0.0f, 1.0f);
  out.sd.Ng = out.sd.N;
  out.sd.wi = out.sd.N;
  out.sd.type = PRIMITIVE_TRIANGLE;
  painterly_svm_trace() = PainterlySvmTrace{};
  const KernelGlobals kg = &globals;
  svm_eval_nodes<node_feature_mask, SHADER_TYPE_SURFACE>(
      kg, nullptr, &out.sd, nullptr, PathRayVisibility(0), uint32_t(0));
  out.trace = painterly_svm_trace();
  painterly_svm_collect(&out.sd, &out.material);
}

double3 d3(const float x, const float y, const float z)
{
  return make_double3(double(x), double(y), double(z));
}

KernelPainterlyLobe lobe(const int kind, const double3 weight, const double ior = 0.0)
{
  return KernelPainterlyLobe{kind, weight, ior};
}

/* One line per lobe, "<kind> <r> <g> <b> <ior>", then "emission <r> <g> <b>" and
 * "dropped <n>". %.17g prints a double that reads back to the same bits, so two descriptions are
 * equal iff the materials are. */
std::string describe(const std::vector<KernelPainterlyLobe> &lobes,
                     const double3 emission,
                     const int num_dropped)
{
  const char *const kinds[] = {"none", "diffuse", "mirror", "glass", "transparent"};
  std::string text;
  char line[256];
  for (const KernelPainterlyLobe &l : lobes) {
    std::snprintf(line,
                  sizeof(line),
                  "%s %.17g %.17g %.17g %.17g\n",
                  (l.kind >= 1 && l.kind <= 4) ? kinds[l.kind] : kinds[0],
                  l.weight.x,
                  l.weight.y,
                  l.weight.z,
                  l.ior);
    text += line;
  }
  std::snprintf(
      line, sizeof(line), "emission %.17g %.17g %.17g\n", emission.x, emission.y, emission.z);
  text += line;
  text += "dropped " + std::to_string(num_dropped) + "\n";
  return text;
}

std::string describe(const PainterlySvmMaterial &material)
{
  return describe(
      std::vector<KernelPainterlyLobe>(material.lobes, material.lobes + material.num_lobes),
      material.emission,
      material.num_dropped);
}

/* lookup_table_read_3D(kg, 1, 1, z, offset, 16, 16, 16) (kernel/util/lookup_table.h:14-74) on
 * the raw `table`, operation by operation. x = y = 1 land on the last grid point, where t = 0
 * and the read returns that entry (:20-23, :37-40); z interpolates between two of them. */
float reference_lookup_corner(const float *table, const float z)
{
  const float zs = saturatef(z) * 15;
  const int index = min(float_to_int(zs), 15);
  const int nindex = min(index + 1, 15);
  const float t = zs - index;
  const float data0 = table[16 * 16 * index + 16 * 15 + 15];
  if (t == 0.0f) {
    return data0;
  }
  const float data1 = table[16 * 16 * nindex + 16 * 15 + 15];
  return (1.0f - t) * data0 + t * data1;
}

/* A Principled BSDF with GGX, Roughness 1, IOR 1.5 and Base Color (0.5, 0.25, 0.125); every
 * other input keeps its default (scene/shader_nodes.cpp:2627-2693). */
ShaderNode *rough_principled(ShaderGraph &graph)
{
  ShaderNode *principled = create_node_by_name(graph, "principled_bsdf");
  set_enum(principled, "distribution", "ggx");
  principled->input("Roughness")->set(1.0f);
  principled->input("IOR")->set(1.5f);
  principled->input("Base Color")->set(make_float3(0.5f, 0.25f, 0.125f));
  return principled;
}

/* The specular and diffuse weights of rough_principled() seen head-on, derived from upstream
 * (kernel/svm/closure.h:426-521):
 * - specular: weight 1; its Fresnel payload has f0 = F0_from_ior(1.5) times Specular Tint 1
 *   (:438-457; F0_from_ior, kernel/closure/bsdf_util.h:290-293);
 * - its albedo: GGX with alpha = Roughness^2 = 1 seen at cos 1 reads ggx_gen_schlick_ior_s at
 *   x = rough = 1, y = cos = 1 and z = sqrt((1.5 - 1) / (1.5 + 1))
 *   (kernel/closure/bsdf_microfacet.h:518-523), then F = mix(f0, 1, s) (:530,
 *   util/math_float3.h:451-454);
 * - diffuse: Base Color times closure_layering_weight(F, 1) = 1 - F
 *   (kernel/closure/bsdf_util.h:440-444; kernel/svm/closure.h:468-470, 515). */
struct PrincipledReference {
  float f0;
  float diffuse;
};

PrincipledReference principled_reference()
{
  const float ior = 1.5f;
  const float f0 = sqr((ior - 1.0f) / (ior + 1.0f));
  const float z = sqrtf(fabsf((ior - 1.0f) / (ior + 1.0f)));
  const float s = reference_lookup_corner(table_ggx_gen_schlick_ior_s, z);
  const float F = f0 + s * (1.0f - f0);
  return PrincipledReference{f0, 1.0f - F};
}

/* A ShaderManager that shows its thin-film table, the upstream member that
 * PainterlyShaderManager uploads (scene/shader.cpp:932-993). Its device hooks do nothing. */
class ThinFilmProbe final : public ShaderManager {
 public:
  const vector<float> &table() const
  {
    return thin_film_table;
  }
  void device_free(Device * /*device*/, DeviceScene * /*dscene*/, Scene * /*scene*/) override {}

 protected:
  void device_update_specific(Device * /*device*/,
                              DeviceScene * /*dscene*/,
                              Scene * /*scene*/,
                              Progress & /*progress*/) override
  {
  }
};

}  // namespace

TEST_CASE("cycles svm closures: the closure node types are registered")
{
  const std::vector<const NodeType *> &types = painterly_cycles_shader_node_types();
  const char *const names[] = {"diffuse_bsdf",
                               "glossy_bsdf",
                               "glass_bsdf",
                               "refraction_bsdf",
                               "transparent_bsdf",
                               "principled_bsdf",
                               "background_shader",
                               "add_closure",
                               "mix_closure"};
  for (const char *name : names) {
    CAPTURE(name);
    const NodeType *type = NodeType::find(ustring(name));
    REQUIRE(type != nullptr);
    CHECK(std::count(types.begin(), types.end(), type) == 1);
  }
}

TEST_CASE("cycles svm closures: the lookup tables are uploaded where KernelTables points")
{
  const unique_ptr<Scene> scene = make_scene();
  unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
  ShaderNode *diffuse = create_node_by_name(*graph, "diffuse_bsdf");
  add_surface(*scene, std::move(graph), diffuse, "BSDF");
  compile(*scene);

  /* ensure_bsdf_table() adds the nine BSDF tables in this order, then the thin-film table
   * (scene/shader.cpp:714-729). LookupTables::add_table() places each after the previous one,
   * rounded up to TABLE_CHUNK_SIZE = 256 floats (scene/tables.cpp:58-95, scene/tables.h:16):
   * 1024, 32 -> 256, 4096, 256, 4096, 256, 3072, 4096, 4096 and 6 * 512 = 3072 entries. */
  const KernelTables &tables = scene->dscene.data.tables;
  CHECK(tables.ggx_E == 0);
  CHECK(tables.ggx_Eavg == 1024);
  CHECK(tables.ggx_glass_E == 1280);
  CHECK(tables.ggx_glass_Eavg == 5376);
  CHECK(tables.ggx_glass_inv_E == 5632);
  CHECK(tables.ggx_glass_inv_Eavg == 9728);
  CHECK(tables.sheen_ltc == 9984);
  CHECK(tables.ggx_gen_schlick_ior_s == 13056);
  CHECK(tables.ggx_gen_schlick_s == 17152);
  CHECK(tables.thin_film_table == 21248);
  REQUIRE(scene->dscene.lookup_table.size() == 24320);

  /* Each table holds the entries of scene/shader.tables. */
  const float *uploaded = scene->dscene.lookup_table.data();
  CHECK(std::memcmp(uploaded + tables.ggx_E, table_ggx_E, sizeof(table_ggx_E)) == 0);
  CHECK(std::memcmp(uploaded + tables.ggx_Eavg, table_ggx_Eavg, sizeof(table_ggx_Eavg)) == 0);
  CHECK(std::memcmp(uploaded + tables.ggx_glass_E, table_ggx_glass_E, sizeof(table_ggx_glass_E)) ==
        0);
  CHECK(std::memcmp(uploaded + tables.ggx_glass_Eavg,
                    table_ggx_glass_Eavg,
                    sizeof(table_ggx_glass_Eavg)) == 0);
  CHECK(std::memcmp(uploaded + tables.ggx_glass_inv_E,
                    table_ggx_glass_inv_E,
                    sizeof(table_ggx_glass_inv_E)) == 0);
  CHECK(std::memcmp(uploaded + tables.ggx_glass_inv_Eavg,
                    table_ggx_glass_inv_Eavg,
                    sizeof(table_ggx_glass_inv_Eavg)) == 0);
  CHECK(std::memcmp(uploaded + tables.sheen_ltc, table_sheen_ltc, sizeof(table_sheen_ltc)) == 0);
  CHECK(std::memcmp(uploaded + tables.ggx_gen_schlick_ior_s,
                    table_ggx_gen_schlick_ior_s,
                    sizeof(table_ggx_gen_schlick_ior_s)) == 0);
  CHECK(std::memcmp(uploaded + tables.ggx_gen_schlick_s,
                    table_ggx_gen_schlick_s,
                    sizeof(table_ggx_gen_schlick_s)) == 0);

  /* The thin-film table is the one every ShaderManager computes in its constructor
   * (scene/shader.cpp:455-460, 1022). Its imaginary DC terms are 0 times a normalization: 0
   * (table_thin_film_cmf[0][3-5], scene/shader.tables). */
  const ThinFilmProbe probe;
  REQUIRE(probe.table().size() == 6 * THIN_FILM_TABLE_SIZE);
  CHECK(std::memcmp(uploaded + tables.thin_film_table,
                    probe.table().data(),
                    sizeof(float) * probe.table().size()) == 0);
  CHECK(uploaded[tables.thin_film_table + 3 * THIN_FILM_TABLE_SIZE] == 0.0f);

  /* KernelGlobalsCPU sees the same array. */
  KernelGlobalsCPU globals;
  PainterlyShaderManager::bind_kernel_globals(scene->dscene, globals);
  CHECK(globals.lookup_table.data == uploaded);
  CHECK(globals.lookup_table.width == 24320);
  CHECK(globals.data.tables.thin_film_table == 21248);

  /* Caustics stay on (PainterlyShaderManager::device_update_common, card T6.7). */
  CHECK(scene->dscene.data.integrator.caustics_reflective == 1);
  CHECK(scene->dscene.data.integrator.caustics_refractive == 1);

  /* A second update frees the tables and adds them again at the same offsets:
   * device_update_specific calls device_free first (scene/svm.cpp:79), and device_free removes the
   * tables (scene/shader.cpp:752-757). */
  compile(*scene);
  CHECK(scene->dscene.data.tables.ggx_gen_schlick_s == 17152);
  CHECK(scene->dscene.data.tables.thin_film_table == 21248);
  CHECK(scene->dscene.lookup_table.size() == 24320);
}

TEST_CASE("cycles svm closures: Diffuse BSDF")
{
  const unique_ptr<Scene> scene = make_scene();
  for (const float roughness : {0.0f, 0.5f}) {
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *diffuse = create_node_by_name(*graph, "diffuse_bsdf");
    diffuse->input("Color")->set(make_float3(0.25f, 0.5f, 0.75f));
    diffuse->input("Roughness")->set(roughness);
    add_surface(*scene, std::move(graph), diffuse, "BSDF");
  }
  compile(*scene);

  /* Weight = Color * mix weight 1 (kernel/svm/closure.h:525-541). Roughness 0 gives a diffuse
   * closure, 0.5 Oren-Nayar; both are the diffuse lobe. No lookup table is read. */
  const std::string expected = describe(
      {lobe(LOBE_DIFFUSE, d3(0.25f, 0.5f, 0.75f))}, make_double3(0.0), 0);
  Evaluation e;
  evaluate(*scene, 0, e);
  CHECK(e.sd.closure[0].type == CLOSURE_BSDF_DIFFUSE_ID);
  CHECK(describe(e.material) == expected);
  CHECK(e.trace.other_arrays == 0);
  evaluate(*scene, 1, e);
  CHECK(e.sd.closure[0].type == CLOSURE_BSDF_OREN_NAYAR_ID);
  CHECK(describe(e.material) == expected);
  CHECK(e.trace.other_arrays == 0);
}

TEST_CASE("cycles svm closures: a linked Color reaches the closure through NODE_CLOSURE_WEIGHT")
{
  /* Compiled without constant folding, as T6.5's prepare_unfolded(): otherwise ColorNode folds
   * into Diffuse.Color. The SurfaceMixWeight of the lone closure is 0 + 1
   * (scene/shader_graph.cpp:1149-1187). */
  const unique_ptr<Scene> scene = make_scene();
  unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
  ShaderNode *color = create_node_by_name(*graph, "color");
  ShaderNode *diffuse = create_node_by_name(*graph, "diffuse_bsdf");
  color->set(*color->type->find_input(ustring("value")), make_float3(0.5f, 0.25f, 0.125f));
  graph->connect(color->output("Color"), diffuse->input("Color"));
  Shader *shader = add_surface(*scene, std::move(graph), diffuse, "BSDF");
  shader->id = 0;
  shader->has_surface = true;
  diffuse->input("SurfaceMixWeight")->set(1.0f);
  Progress progress;
  shader_manager(*scene).device_update_post(nullptr, &scene->dscene, scene.get(), progress);
  shader_manager(*scene).device_update_lookup_tables(&scene->dscene, scene.get());

  /* BsdfNode::compile emits NODE_CLOSURE_WEIGHT for a linked Color, NODE_CLOSURE_SET_WEIGHT
   * otherwise (scene/shader_nodes.cpp:2189-2214). */
  const int *usage = reinterpret_cast<const int *>(&scene->dscene.data.svm_usage);
  CHECK(usage[NODE_CLOSURE_WEIGHT] != 0);
  CHECK(usage[NODE_CLOSURE_SET_WEIGHT] == 0);

  Evaluation e;
  evaluate(*scene, 0, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_DIFFUSE, d3(0.5f, 0.25f, 0.125f))}, make_double3(0.0), 0));
}

TEST_CASE("cycles svm closures: Glossy BSDF")
{
  const unique_ptr<Scene> scene = make_scene();
  {
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *glossy = create_node_by_name(*graph, "glossy_bsdf");
    set_enum(glossy, "distribution", "ggx");
    glossy->input("Color")->set(make_float3(0.5f, 0.25f, 1.0f));
    add_surface(*scene, std::move(graph), glossy, "BSDF");
  }
  {
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *glossy = create_node_by_name(*graph, "glossy_bsdf");
    set_enum(glossy, "distribution", "multi_ggx");
    glossy->input("Color")->set(make_float3(1.0f, 1.0f, 1.0f));
    add_surface(*scene, std::move(graph), glossy, "BSDF");
  }
  compile(*scene);

  /* GGX: weight = Color * mix weight 1, no Fresnel payload (kernel/svm/closure.h:662-735), so
   * the mirror lobe is Color. No lookup table is read. */
  Evaluation e;
  evaluate(*scene, 0, e);
  CHECK(e.sd.closure[0].type == CLOSURE_BSDF_MICROFACET_GGX_ID);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_MIRROR, d3(0.5f, 0.25f, 1.0f))}, make_double3(0.0), 0));
  CHECK(e.trace.other_arrays == 0);

  /* Multiscatter GGX: energy preservation reads ggx_E and ggx_Eavg
   * (kernel/closure/bsdf_microfacet.h:432-485, 1025-1036). alpha = Roughness 0.5 squared, so
   * rough = sqrt(sqrt(0.25 * 0.25)) = 0.5, which falls between two of the 32 entries: two reads
   * from each table. A white Color gives Fss = 1, which leaves the weight unchanged (:472). */
  evaluate(*scene, 1, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_MIRROR, d3(1.0f, 1.0f, 1.0f))}, make_double3(0.0), 0));
  CHECK(e.trace.other_arrays == 4);
}

TEST_CASE("cycles svm closures: Glass and Refraction BSDF")
{
  const unique_ptr<Scene> scene = make_scene();
  const struct {
    const char *type;
    float3 color;
    float ior;
  } shaders[] = {{"glass_bsdf", make_float3(0.5f, 0.25f, 1.0f), 1.45f},
                 {"glass_bsdf", make_float3(1.0f, 1.0f, 1.0f), 1.5f},
                 {"refraction_bsdf", make_float3(0.5f, 0.25f, 1.0f), 1.25f}};
  for (const auto &s : shaders) {
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *glass = create_node_by_name(*graph, s.type);
    set_enum(glass, "distribution", "ggx");
    glass->input("Color")->set(s.color);
    glass->input("IOR")->set(s.ior);
    add_surface(*scene, std::move(graph), glass, "BSDF");
  }
  compile(*scene);

  /* Glass: weight = mix weight 1, Color in the Fresnel payload's transmission tint
   * (kernel/svm/closure.h:779-845). The albedo estimate reads ggx_gen_schlick_ior_s at
   * z = sqrt((IOR - 1) / (IOR + 1)), between two grid points: two reads
   * (kernel/closure/bsdf_microfacet.h:518-523). */
  Evaluation e;
  evaluate(*scene, 0, e);
  CHECK(e.sd.closure[0].type == CLOSURE_BSDF_MICROFACET_GGX_GLASS_ID);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_GLASS, d3(0.5f, 0.25f, 1.0f), double(1.45f))}, make_double3(0.0), 0));
  CHECK(e.trace.other_arrays == 2);

  /* A white Glass BSDF is smallpaint's glass: unit weight, its IOR (SPEC §6, §9). */
  evaluate(*scene, 1, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_GLASS, d3(1.0f, 1.0f, 1.0f), 1.5)}, make_double3(0.0), 0));

  /* Refraction: weight = Color * mix weight 1, no Fresnel payload (kernel/svm/closure.h:737-777).
   */
  evaluate(*scene, 2, e);
  CHECK(e.sd.closure[0].type == CLOSURE_BSDF_MICROFACET_GGX_REFRACTION_ID);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_GLASS, d3(0.5f, 0.25f, 1.0f), 1.25)}, make_double3(0.0), 0));
  CHECK(e.trace.other_arrays == 0);
}

TEST_CASE("cycles svm closures: Transparent BSDF")
{
  const unique_ptr<Scene> scene = make_scene();
  unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
  ShaderNode *transparent = create_node_by_name(*graph, "transparent_bsdf");
  transparent->input("Color")->set(make_float3(0.5f, 0.5f, 0.25f));
  add_surface(*scene, std::move(graph), transparent, "BSDF");
  compile(*scene);

  /* bsdf_transparent_setup (kernel/closure/bsdf_transparent.h:16-62). */
  Evaluation e;
  evaluate(*scene, 0, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_TRANSPARENT, d3(0.5f, 0.5f, 0.25f))}, make_double3(0.0), 0));
}

TEST_CASE("cycles svm closures: Emission and Background")
{
  const unique_ptr<Scene> scene = make_scene();
  {
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *emission = create_node_by_name(*graph, "emission");
    emission->input("Color")->set(make_float3(0.25f, 0.5f, 1.0f));
    emission->input("Strength")->set(4.0f);
    add_surface(*scene, std::move(graph), emission, "Emission");
  }
  {
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *background = create_node_by_name(*graph, "background_shader");
    background->input("Color")->set(make_float3(0.5f, 0.25f, 1.0f));
    background->input("Strength")->set(2.0f);
    shader_manager(*scene).background_shader = add_surface(
        *scene, std::move(graph), background, "Background");
  }
  compile(*scene);

  /* Emission: Color * Strength (scene/shader_nodes.cpp:3085-3092). No closure gives a lobe, so
   * the material is smallpaint's light: one diffuse lobe of weight 0 (SPEC §6). */
  Evaluation e;
  evaluate(*scene, 0, e);
  CHECK(e.sd.num_closure == 0);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_DIFFUSE, make_double3(0.0))}, make_double3(1.0, 2.0, 4.0), 0));

  /* Background, with the mask of Cycles' background evaluation: Color * Strength
   * (scene/shader_nodes.cpp:3133-3160, kernel/svm/closure.h:1432-1451). */
  evaluate<painterly_svm_background_feature_mask>(*scene, 1, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_DIFFUSE, make_double3(0.0))}, make_double3(1.0, 0.5, 2.0), 0));
}

TEST_CASE("cycles svm closures: Mix Shader and Add Shader")
{
  const unique_ptr<Scene> scene = make_scene();
  {
    /* Mix Shader, Fac 0.25: Diffuse gets 1 - 0.25, Glossy 0.25 (MixClosureWeightNode,
     * kernel/svm/closure.h:1499-1515). */
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *mix = create_node_by_name(*graph, "mix_closure");
    ShaderNode *diffuse = create_node_by_name(*graph, "diffuse_bsdf");
    ShaderNode *glossy = create_node_by_name(*graph, "glossy_bsdf");
    set_enum(glossy, "distribution", "ggx");
    mix->input("Fac")->set(0.25f);
    diffuse->input("Color")->set(make_float3(1.0f, 0.5f, 0.25f));
    glossy->input("Color")->set(make_float3(0.5f, 1.0f, 0.25f));
    graph->connect(diffuse->output("BSDF"), mix->input("Closure1"));
    graph->connect(glossy->output("BSDF"), mix->input("Closure2"));
    add_surface(*scene, std::move(graph), mix, "Closure");
  }
  {
    /* Mix Shader, Fac 0.5, of Emission (Color (1, 0.5, 0.25), Strength 2) and Diffuse. */
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *mix = create_node_by_name(*graph, "mix_closure");
    ShaderNode *emission = create_node_by_name(*graph, "emission");
    ShaderNode *diffuse = create_node_by_name(*graph, "diffuse_bsdf");
    mix->input("Fac")->set(0.5f);
    emission->input("Color")->set(make_float3(1.0f, 0.5f, 0.25f));
    emission->input("Strength")->set(2.0f);
    diffuse->input("Color")->set(make_float3(0.5f, 0.5f, 0.5f));
    graph->connect(emission->output("Emission"), mix->input("Closure1"));
    graph->connect(diffuse->output("BSDF"), mix->input("Closure2"));
    add_surface(*scene, std::move(graph), mix, "Closure");
  }
  {
    /* Add Shader of Diffuse and Transparent: both keep weight 1
     * (scene/shader_graph.cpp:1135-1146). */
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *add = create_node_by_name(*graph, "add_closure");
    ShaderNode *diffuse = create_node_by_name(*graph, "diffuse_bsdf");
    ShaderNode *transparent = create_node_by_name(*graph, "transparent_bsdf");
    diffuse->input("Color")->set(make_float3(0.5f, 0.25f, 0.125f));
    transparent->input("Color")->set(make_float3(0.25f, 0.25f, 0.25f));
    graph->connect(diffuse->output("BSDF"), add->input("Closure1"));
    graph->connect(transparent->output("BSDF"), add->input("Closure2"));
    add_surface(*scene, std::move(graph), add, "Closure");
  }
  compile(*scene);

  const int *usage = reinterpret_cast<const int *>(&scene->dscene.data.svm_usage);
  CHECK(usage[NODE_MIX_CLOSURE] != 0);

  /* Closures appear in the order of Closure1, then Closure2 (SVMCompiler::generate_multi_closure,
   * scene/svm.cpp:845-997). */
  Evaluation e;
  evaluate(*scene, 0, e);
  CHECK(describe(e.material) == describe({lobe(LOBE_DIFFUSE, d3(0.75f, 0.375f, 0.1875f)),
                                          lobe(LOBE_MIRROR, d3(0.125f, 0.25f, 0.0625f))},
                                         make_double3(0.0),
                                         0));
  evaluate(*scene, 1, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_DIFFUSE, d3(0.25f, 0.25f, 0.25f))}, make_double3(1.0, 0.5, 0.25), 0));
  evaluate(*scene, 2, e);
  CHECK(describe(e.material) == describe({lobe(LOBE_DIFFUSE, d3(0.5f, 0.25f, 0.125f)),
                                          lobe(LOBE_TRANSPARENT, d3(0.25f, 0.25f, 0.25f))},
                                         make_double3(0.0),
                                         0));
}

TEST_CASE("cycles svm closures: Principled BSDF layers and the lookup tables")
{
  const unique_ptr<Scene> scene = make_scene();
  /* 0: rough_principled(). 1: Specular IOR Level 0. 2: Metallic 1. 3: Transmission Weight 1 and
   * Base Color (0.25, 0.0625, 1). 4: Alpha 0.5. 5: Emission Color (0.5, 0.25, 1), Strength 2. */
  for (int variant = 0; variant < 6; variant++) {
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *principled = rough_principled(*graph);
    switch (variant) {
      case 1:
        principled->input("Specular IOR Level")->set(0.0f);
        break;
      case 2:
        principled->input("Metallic")->set(1.0f);
        break;
      case 3:
        principled->input("Transmission Weight")->set(1.0f);
        principled->input("Base Color")->set(make_float3(0.25f, 0.0625f, 1.0f));
        break;
      case 4:
        principled->input("Alpha")->set(0.5f);
        break;
      case 5:
        principled->input("Emission Color")->set(make_float3(0.5f, 0.25f, 1.0f));
        principled->input("Emission Strength")->set(2.0f);
        break;
    }
    add_surface(*scene, std::move(graph), principled, "BSDF");
  }
  compile(*scene);
  const PrincipledReference r = principled_reference();
  Evaluation e;

  /* The specular layer is a mirror lobe of f0 (its Fresnel payload at normal incidence). Under it,
   * the diffuse lobe is Base Color * (1 - F), F from the lookup table. Two albedo estimates read
   * the table, two entries each: the specular setup (kernel/closure/bsdf_microfacet.h:973) and
   * the layering (kernel/svm/closure.h:470). */
  evaluate(*scene, 0, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_MIRROR, d3(r.f0, r.f0, r.f0)),
                  lobe(LOBE_DIFFUSE, d3(0.5f * r.diffuse, 0.25f * r.diffuse, 0.125f * r.diffuse))},
                 make_double3(0.0),
                 0));
  CHECK(e.trace.other_arrays == 4);

  /* Specular IOR Level 0: f0 = 0, eta = 1, no specular layer (kernel/svm/closure.h:426-438). The
   * diffuse lobe is Base Color, and no table is read: the lookup table is what changes it. */
  evaluate(*scene, 1, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_DIFFUSE, d3(0.5f, 0.25f, 0.125f))}, make_double3(0.0), 0));
  CHECK(e.trace.other_arrays == 0);

  /* Metallic 1: one F82 conductor of weight 1 whose payload f0 is Base Color; the layers below get
   * weight 0 (kernel/svm/closure.h:320-352). Its albedo estimate reads ggx_gen_schlick_s at
   * z = 0.5, between two grid points (kernel/closure/bsdf_microfacet.h:545-547). */
  evaluate(*scene, 2, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_MIRROR, d3(0.5f, 0.25f, 0.125f))}, make_double3(0.0), 0));
  CHECK(e.trace.other_arrays == 2);

  /* Transmission Weight 1: one glass of weight 1 whose transmission tint is sqrt(Base Color)
   * (kernel/svm/closure.h:405-410); the layers below get weight 0. */
  evaluate(*scene, 3, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_GLASS, d3(0.5f, 0.25f, 1.0f), 1.5)}, make_double3(0.0), 0));

  /* Alpha 0.5: a transparent closure of 1 - 0.5 first, then every layer at weight 0.5
   * (kernel/svm/closure.h:108-113); 0.5 * F / 0.5 = F, so the diffuse lobe halves. */
  evaluate(*scene, 4, e);
  CHECK(describe(e.material) ==
        describe(
            {lobe(LOBE_TRANSPARENT, d3(0.5f, 0.5f, 0.5f)),
             lobe(LOBE_MIRROR, d3(0.5f * r.f0, 0.5f * r.f0, 0.5f * r.f0)),
             lobe(LOBE_DIFFUSE, d3(0.25f * r.diffuse, 0.125f * r.diffuse, 0.0625f * r.diffuse))},
            make_double3(0.0),
            0));

  /* Emission Color * Emission Strength, not attenuated without coat or sheen
   * (kernel/svm/closure.h:205-210). */
  evaluate(*scene, 5, e);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_MIRROR, d3(r.f0, r.f0, r.f0)),
                  lobe(LOBE_DIFFUSE, d3(0.5f * r.diffuse, 0.25f * r.diffuse, 0.125f * r.diffuse))},
                 make_double3(1.0, 0.5, 2.0),
                 0));
}

TEST_CASE("cycles svm closures: Principled sheen and subsurface and thin wall follow the policy")
{
  const unique_ptr<Scene> scene = make_scene();
  /* 0: Sheen Weight 1. 1: Subsurface Weight 1. 2: Thin Wall and Transmission Weight 1. */
  for (int variant = 0; variant < 3; variant++) {
    unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
    ShaderNode *principled = rough_principled(*graph);
    if (variant == 0) {
      principled->input("Sheen Weight")->set(1.0f);
    }
    else if (variant == 1) {
      principled->input("Subsurface Weight")->set(1.0f);
    }
    else {
      principled->input("Thin Wall")->set(1);
      principled->input("Transmission Weight")->set(1.0f);
    }
    add_surface(*scene, std::move(graph), principled, "BSDF");
  }
  compile(*scene);
  const PrincipledReference r = principled_reference();
  Evaluation e;

  /* Sheen is the top layer (kernel/svm/closure.h:115-144): a diffuse lobe. */
  evaluate(*scene, 0, e);
  REQUIRE(e.material.num_lobes == 3);
  CHECK(e.sd.closure[0].type == CLOSURE_BSDF_SHEEN_ID);
  CHECK(e.material.lobes[0].kind == LOBE_DIFFUSE);
  CHECK(e.material.lobes[1].kind == LOBE_MIRROR);
  CHECK(e.material.lobes[2].kind == LOBE_DIFFUSE);

  /* Subsurface Weight 1: the BSSRDF takes Base Color * (1 - F) and the diffuse closure weight 0
   * (kernel/svm/closure.h:474-521). The BSSRDF is the diffuse lobe: the same lobes as variant 0
   * of the previous test case. */
  evaluate(*scene, 1, e);
  REQUIRE(e.sd.num_closure == 2);
  CHECK(e.sd.closure[1].type == CLOSURE_BSSRDF_RANDOM_WALK_ID);
  CHECK(describe(e.material) ==
        describe({lobe(LOBE_MIRROR, d3(r.f0, r.f0, r.f0)),
                  lobe(LOBE_DIFFUSE, d3(0.5f * r.diffuse, 0.25f * r.diffuse, 0.125f * r.diffuse))},
                 make_double3(0.0),
                 0));

  /* Thin Wall: thin-glass reflection, a mirror lobe, and thin-glass transmission, which does not
   * bend the ray: a transparent lobe (kernel/closure/bsdf_microfacet.h:1366-1400). */
  evaluate(*scene, 2, e);
  REQUIRE(e.sd.num_closure == 2);
  CHECK(e.sd.closure[0].type == CLOSURE_BSDF_MICROFACET_GGX_ID);
  CHECK(e.sd.closure[1].type == CLOSURE_BSDF_THIN_GLASS_TRANSMISSION_ID);
  REQUIRE(e.material.num_lobes == 2);
  CHECK(e.material.lobes[0].kind == LOBE_MIRROR);
  CHECK(e.material.lobes[1].kind == LOBE_TRANSPARENT);
}

TEST_CASE("cycles svm closures: the collector on hand-made closures")
{
  /* Closures set up directly with the vendored setup functions, for the categories that no node
   * of card T6.7 emits. */
  ShaderData sd = painterly_svm_test_shader_data(0);
  sd.N = make_float3(0.0f, 0.0f, 1.0f);
  sd.Ng = sd.N;
  sd.wi = sd.N;
  /* Without SD_EMISSION the emission is zero, whatever closure_emission_background holds
   * (kernel/closure/emissive.h:29-38). */
  sd.closure_emission_background = make_float3(1.0f, 2.0f, 3.0f);

  bsdf_translucent_setup(&sd, sd.N, make_float3(0.5f, 0.25f, 0.125f));
  closure_alloc(&sd, sizeof(ShaderClosure), CLOSURE_HOLDOUT_ID, make_float3(1.0f, 1.0f, 1.0f));
  closure_alloc(&sd, sizeof(ShaderClosure), CLOSURE_NONE_ID, make_float3(1.0f, 1.0f, 1.0f));
  bsdf_transparent_setup(&sd, make_float3(0.25f, 0.25f, 0.25f), 0);
  /* A physical conductor, set up as kernel/svm/closure.h:572-630 does, without the albedo
   * estimate. Its colour is fresnel_conductor() at normal incidence: the same vendored
   * function, so this checks the collector's dispatch on fresnel_type, not the formula. */
  MicrofacetBsdf *conductor = (MicrofacetBsdf *)bsdf_alloc(
      &sd, sizeof(MicrofacetBsdf), make_float3(0.5f, 0.5f, 0.5f));
  REQUIRE(conductor != nullptr);
  conductor->N = sd.N;
  conductor->T = zero_float3();
  conductor->ior = 1.0f;
  conductor->alpha_x = conductor->alpha_y = 0.25f;
  sd.flag |= bsdf_microfacet_ggx_setup(conductor);
  FresnelConductor *fresnel = (FresnelConductor *)closure_alloc_extra(&sd,
                                                                      sizeof(FresnelConductor));
  REQUIRE(fresnel != nullptr);
  fresnel->thin_film.thickness = 0.0f;
  fresnel->thin_film.ior = 1.0f;
  fresnel->ior = {make_float3(2.0f, 1.5f, 1.25f), make_float3(0.0f, 0.5f, 1.0f)};
  conductor->fresnel_type = MicrofacetFresnel::CONDUCTOR;
  conductor->fresnel = fresnel;
  const float3 conductor_color = fresnel_conductor(1.0f, fresnel->ior);

  PainterlySvmMaterial material;
  painterly_svm_collect(&sd, &material);
  CHECK(describe(material) == describe({lobe(LOBE_DIFFUSE, d3(0.5f, 0.25f, 0.125f)),
                                        lobe(LOBE_TRANSPARENT, d3(0.25f, 0.25f, 0.25f)),
                                        lobe(LOBE_MIRROR,
                                             make_double3(0.5 * double(conductor_color.x),
                                                          0.5 * double(conductor_color.y),
                                                          0.5 * double(conductor_color.z)))},
                                       make_double3(0.0),
                                       1));

  /* Only a holdout: dropped, and the lobe of weight 0 (SPEC §6). */
  ShaderData holdout = painterly_svm_test_shader_data(0);
  closure_alloc(
      &holdout, sizeof(ShaderClosure), CLOSURE_HOLDOUT_ID, make_float3(1.0f, 1.0f, 1.0f));
  painterly_svm_collect(&holdout, &material);
  CHECK(describe(material) ==
        describe({lobe(LOBE_DIFFUSE, make_double3(0.0))}, make_double3(0.0), 1));

  /* The policy, type by type (painterly_svm_lobe_kind). */
  int kind = 0;
  CHECK(painterly_svm_lobe_kind(CLOSURE_BSDF_SHEEN_ID, &kind));
  CHECK(kind == LOBE_DIFFUSE);
  CHECK(painterly_svm_lobe_kind(CLOSURE_BSSRDF_BURLEY_ID, &kind));
  CHECK(kind == LOBE_DIFFUSE);
  CHECK(painterly_svm_lobe_kind(CLOSURE_BSDF_HAIR_TRANSMISSION_ID, &kind));
  CHECK(kind == LOBE_TRANSPARENT);
  CHECK(painterly_svm_lobe_kind(CLOSURE_BSDF_ASHIKHMIN_VELVET_ID, &kind));
  CHECK(kind == LOBE_MIRROR);
  CHECK(painterly_svm_lobe_kind(CLOSURE_BSDF_MICROFACET_BECKMANN_GLASS_ID, &kind));
  CHECK(kind == LOBE_GLASS);
  CHECK_FALSE(painterly_svm_lobe_kind(CLOSURE_BSDF_RAY_PORTAL_ID, &kind));
  CHECK_FALSE(painterly_svm_lobe_kind(CLOSURE_VOLUME_HENYEY_GREENSTEIN_ID, &kind));
}

CCL_NAMESPACE_END
