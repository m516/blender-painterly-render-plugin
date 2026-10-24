/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Cycles' image texture SVM nodes (card T6.8), run through the generated svm_eval_nodes() of
 * cycles_svm on hand-encoded byte code (cycles_svm_test_support.h, T6.3), with images loaded by
 * the in-memory ImageManager of the shim scene/image.h.
 *
 * Every expected value is an evaluation of the upstream definition that does not run the code
 * under test:
 * - closest and linear interpolation sample images of small integers at points whose weights
 *   are dyadic, so every intermediate result is exactly representable in float32 and nothing
 *   rounds; the expected values are written out, with the texels and weights that give them;
 * - cubic interpolation samples a delta image (one texel 1, all others 0). Only the taps that land
 *   on that texel contribute, so each expected value is a short expression in the B-spline
 *   weights, written out per extension in the kernel's order of operations. At a texel centre
 *   (t = 0) the weights are the constants 1/6, 2/3, 1/6, 0 of the B-spline
 *   (kernel/device/cpu/image.h:21-28). Elsewhere cubic_weights_reference() evaluates the same
 *   polynomials operation by operation;
 * - byte texels are read as b * (1 / 255) (kernel/device/cpu/image.h:54-58), half texels exactly;
 * - the sRGB case compares with color_srgb_to_linear_v4() of util/color.h (card T3.2), the
 *   function that the kernel applies after interpolation (kernel/svm/image.h:33-35).
 * check_equal() compares inside the VM with exact equality (T6.3). Evaluation draws no random
 * number: lcg_state is 0 (painterly_svm_test_shader_data, T6.3), and untiled images never read it
 * (kernel/util/image_2d.h:102 is reached only for tiled images). */

#include "cycles_svm_test_scene.h"

#include "scene/image.h"
#include "util/color.h"

#include <climits>
#include <limits>
#include <string>

#include <doctest/doctest.h>

CCL_NAMESPACE_BEGIN

namespace {

/* Stack slots of one sample: the coordinate at 0-2 (0-8 for a *_DERIVATIVE case), the colour at
 * 10-12, the alpha at 13. */
constexpr SVMStackOffset co_slot = 0;
constexpr SVMStackOffset color_slot = 10;
constexpr SVMStackOffset alpha_slot = 13;

/* run_and_check() of card T6.6 (test_cycles_svm_textures.cpp): append NODE_END, run, and check
 * the fetch trace, the number of fetches from kernel arrays other than svm_nodes, and that no
 * in-VM check failed. */
void run_and_check(KernelGlobalsCPU &globals,
                   PainterlySvmTestProgram &program,
                   ShaderData &sd,
                   const int other_arrays)
{
  program.add_node(NODE_END);
  const PainterlySvmTrace trace = painterly_svm_test_run_shader_data(globals, program, sd);
  CHECK(program.fetched_trace(trace.svm_nodes) == program.expected_trace(0));
  CHECK(trace.other_arrays == other_arrays);
  CHECK(program.failed_checks(trace.svm_nodes) == "");
}

/* A program for shader 0 whose jump entry points at the first node added (T6.3). */
PainterlySvmTestProgram new_program()
{
  PainterlySvmTestProgram program;
  const int start = program.size();
  program.set_jump(0, start, start, start);
  return program;
}

/* Points the kernel arrays image_textures and image_info of `globals` at `manager`'s. */
void bind_images(KernelGlobalsCPU &globals, const ImageManager &manager)
{
  globals.image_textures.data = manager.get_image_textures().data();
  globals.image_textures.width = int(manager.get_image_textures().size());
  globals.image_info.data = manager.get_image_info().data();
  globals.image_info.width = int(manager.get_image_info().size());
}

/* Checks the colour and alpha outputs of the sample just added. */
void check_sample(PainterlySvmTestProgram &program,
                  const float4 expected,
                  const std::string &label)
{
  program.check_equal3(color_slot, make_float3(expected.x, expected.y, expected.z), label);
  program.check_equal(alpha_slot, expected.w, label + ".alpha");
}

/* Writes the coordinate (u, v, 0) to the stack, samples image `id` with NODE_TEX_IMAGE and flat
 * projection, and checks the result. One sample makes two fetches from other kernel arrays,
 * image_textures and image_info (kernel/device/cpu/image.h:336, 364). */
void add_sample(PainterlySvmTestProgram &program,
                const int id,
                const float u,
                const float v,
                const float4 expected,
                const std::string &label,
                const uint flags = 0)
{
  program.add_node(NODE_VALUE_V,
                   SVMNodeValueV{.out_offset = co_slot, .value = make_float3(u, v, 0.0f)});
  program.add_node(NODE_TEX_IMAGE,
                   SVMNodeTexImage{.id = id,
                                   .projection = NODE_IMAGE_PROJ_FLAT,
                                   .flags = uint8_t(flags),
                                   .co = co_slot,
                                   .out_offset = color_slot,
                                   .alpha_offset = alpha_slot});
  check_sample(program, expected, label);
}

ImageParams params(const InterpolationType interpolation,
                   const ExtensionType extension,
                   const ImageAlphaType alpha_type = IMAGE_ALPHA_AUTO)
{
  ImageParams result;
  result.interpolation = interpolation;
  result.extension = extension;
  result.alpha_type = alpha_type;
  return result;
}

/* A float image in scene linear with associated alpha, as Blender holds a float buffer. */
PainterlyImagePixels float_image(const int width, const int height, const vector<float4> &floats)
{
  PainterlyImagePixels pixels;
  pixels.width = width;
  pixels.height = height;
  pixels.source_type = IMAGE_DATA_TYPE_FLOAT4;
  pixels.colorspace = PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR;
  pixels.is_unassociated_alpha = false;
  pixels.floats = floats;
  return pixels;
}

/* A byte image with unassociated alpha, as Blender holds a byte buffer. */
PainterlyImagePixels byte_image(const int width,
                                const int height,
                                const PainterlyImageColorSpace colorspace,
                                const vector<uchar4> &bytes)
{
  PainterlyImagePixels pixels;
  pixels.width = width;
  pixels.height = height;
  pixels.source_type = IMAGE_DATA_TYPE_BYTE4;
  pixels.colorspace = colorspace;
  pixels.is_unassociated_alpha = true;
  pixels.bytes = bytes;
  return pixels;
}

/* The 4 x 2 value image. Texel (x, y) is (1 + x, 1 + y, n, n / 16) with n = 1 + x + 4y: every
 * texel differs, blue names the texel, and alpha is blue / 16. Row y = 0 is at v = 0. */
PainterlyImagePixels value_image()
{
  vector<float4> floats;
  for (int y = 0; y < 2; y++) {
    for (int x = 0; x < 4; x++) {
      const float n = float(1 + x + 4 * y);
      floats.push_back(make_float4(float(1 + x), float(1 + y), n, n / 16.0f));
    }
  }
  return float_image(4, 2, floats);
}

/* Texel (x, y) of value_image(). */
float4 texel(const int x, const int y)
{
  const float n = float(1 + x + 4 * y);
  return make_float4(float(1 + x), float(1 + y), n, n / 16.0f);
}

/* The 4 x 2 delta image: (1, 1, 1, 1) at texel (0, 0), zero elsewhere. */
PainterlyImagePixels delta_image()
{
  vector<float4> floats(8, zero_float4());
  floats[0] = one_float4();
  return float_image(4, 2, floats);
}

/* The four extensions, in the order of the test tables, with their ImageTextureNode names
 * (scene/shader_nodes.cpp:268-273). */
const ExtensionType extensions[4] = {
    EXTENSION_REPEAT, EXTENSION_EXTEND, EXTENSION_CLIP, EXTENSION_MIRROR};
const char *const extension_names[4] = {"periodic", "clamp", "black", "mirror"};

/* SET_CUBIC_SPLINE_WEIGHTS (kernel/device/cpu/image.h:21-28), operation by operation: the cubic
 * B-spline weights of the taps at -1, 0, +1, +2 for a fractional position t. */
void cubic_weights_reference(const float t, float w[4])
{
  w[0] = (((-1.0f / 6.0f) * t + 0.5f) * t - 0.5f) * t + (1.0f / 6.0f);
  w[1] = ((0.5f * t - 1.0f) * t) * t + (2.0f / 3.0f);
  w[2] = ((-0.5f * t + 0.5f) * t + 0.5f) * t + (1.0f / 6.0f);
  w[3] = (1.0f / 6.0f) * t * t * t;
}

}  // namespace

/* Closest: the texel (ix, iy) that frac() gives for x = u * width and y = v * height, wrapped by
 * the extension (kernel/device/cpu/image.h:135-168, 110-131). frac() is floor() except at
 * negative integers (kernel/device/cpu/image.h:30-35). */
TEST_CASE("cycles svm images: closest interpolation and the four extensions")
{
  ImageManager manager;
  int ids[4];
  for (int e = 0; e < 4; e++) {
    ids[e] =
        manager.add_image(value_image(), params(INTERPOLATION_CLOSEST, extensions[e])).kernel_id();
  }
  KernelGlobalsCPU globals;
  bind_images(globals, manager);

  /* (0.375, 0.25): x = 1.5, y = 0.5, texel (1, 0) for every extension.
   * (-0.375, 1.75): x = -1.5, y = 3.5, so ix = -2, iy = 3 before wrapping:
   *   periodic: (2, 1); clamp: (0, 1); black: outside, zero; mirror: (1, 0)
   *   (wrap_mirror: |-2 + 1| % 8 = 1; 3 % 4 = 3 >= 2, so 2 * 2 - 3 - 1 = 0).
   * (-0.25, 0.25): x = -1 exactly. frac() truncates and then subtracts 1 for every negative x
   * (kernel/device/cpu/image.h:30-35), so a negative integer x gives ix = x - 1 = -2, not
   * floor(x) = -1; y = 0.5, iy = 0:
   *   periodic: (2, 0); clamp: (0, 0); black: zero; mirror: (1, 0). */
  const float4 inside = texel(1, 0);
  const float4 outside[4] = {texel(2, 1), texel(0, 1), zero_float4(), texel(1, 0)};
  const float4 negative_integer[4] = {texel(2, 0), texel(0, 0), zero_float4(), texel(1, 0)};

  PainterlySvmTestProgram program = new_program();
  for (int e = 0; e < 4; e++) {
    const std::string name = extension_names[e];
    add_sample(program, ids[e], 0.375f, 0.25f, inside, name + " inside");
    add_sample(program, ids[e], -0.375f, 1.75f, outside[e], name + " outside");
    add_sample(program, ids[e], -0.25f, 0.25f, negative_integer[e], name + " negative integer x");
  }
  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 2 * 12);
}

/* Linear: x = u * width - 0.5 and y = v * height - 0.5 split into ix + tx and iy + ty; the four
 * texels (ix, iy), (ix + 1, iy), (ix, iy + 1), (ix + 1, iy + 1) weigh (1 - ty)(1 - tx),
 * (1 - ty) tx, ty (1 - tx) and ty tx (kernel/device/cpu/image.h:170-222). */
TEST_CASE("cycles svm images: linear interpolation and the four extensions")
{
  ImageManager manager;
  int ids[4];
  for (int e = 0; e < 4; e++) {
    ids[e] =
        manager.add_image(value_image(), params(INTERPOLATION_LINEAR, extensions[e])).kernel_id();
  }
  KernelGlobalsCPU globals;
  bind_images(globals, manager);

  /* (0.4375, 0.5): x = 1.25, y = 0.5, so tx = 0.25, ty = 0.5 and the texels (1, 0), (2, 0),
   * (1, 1), (2, 1) weigh 0.375, 0.125, 0.375, 0.125, for every extension:
   *   red 0.375 * 2 + 0.125 * 3 + 0.375 * 2 + 0.125 * 3 = 2.25; green 1.5;
   *   blue 0.375 * 2 + 0.125 * 3 + 0.375 * 6 + 0.125 * 7 = 4.25; alpha = blue / 16. */
  const float4 inside = make_float4(2.25f, 1.5f, 4.25f, 4.25f / 16.0f);
  /* (-0.3125, 0.5): x = -1.75, so ix = -2, tx = 0.25; y as above. The column pair (ix, ix + 1) is
   *   periodic (2, 3): red 3.25, green 1.5, blue 0.375 * 3 + 0.125 * 4 + 0.375 * 7 + 0.125 * 8;
   *   clamp (0, 0): red 1, green 1.5, blue 0.5 * 1 + 0.5 * 5;
   *   black: ix < -1, so zero (kernel/device/cpu/image.h:190-194);
   *   mirror (1, 0): red 1.75, green 1.5, blue 0.375 * 2 + 0.125 * 1 + 0.375 * 6 + 0.125 * 5. */
  const float4 outside[4] = {make_float4(3.25f, 1.5f, 5.25f, 5.25f / 16.0f),
                             make_float4(1.0f, 1.5f, 3.0f, 3.0f / 16.0f),
                             zero_float4(),
                             make_float4(1.75f, 1.5f, 3.75f, 3.75f / 16.0f)};

  PainterlySvmTestProgram program = new_program();
  for (int e = 0; e < 4; e++) {
    const std::string name = extension_names[e];
    add_sample(program, ids[e], 0.4375f, 0.5f, inside, name + " inside");
    add_sample(program, ids[e], -0.3125f, 0.5f, outside[e], name + " outside");
  }
  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 2 * 8);
}

/* Cubic: x = u * width - 0.5 = ix + tx; the taps ix - 1, ix, ix + 1, ix + 2 weigh the B-spline
 * weights of tx, likewise in y; the result sums, row tap by row tap, the row weight times the
 * weighted sum of the row's four texels (kernel/device/cpu/image.h:224-311). On the delta image
 * only taps that land on texel (0, 0) contribute. A = 2/3 and B = 1/6 are the weights of the
 * taps ix and ix +/- 1 at a texel centre (t = 0); the tap ix + 2 weighs 0 there. */
TEST_CASE("cycles svm images: cubic interpolation and the four extensions")
{
  ImageManager manager;
  int ids[4];
  for (int e = 0; e < 4; e++) {
    ids[e] =
        manager.add_image(delta_image(), params(INTERPOLATION_CUBIC, extensions[e])).kernel_id();
  }
  /* INTERPOLATION_SMART is cubic on the CPU (kernel/device/cpu/image.h:320-321). */
  const int smart_id =
      manager.add_image(delta_image(), params(INTERPOLATION_SMART, EXTENSION_REPEAT)).kernel_id();
  KernelGlobalsCPU globals;
  bind_images(globals, manager);

  const float A = 2.0f / 3.0f;
  const float B = 1.0f / 6.0f;
  float w[4];
  cubic_weights_reference(0.5f, w);
  float v[4];
  cubic_weights_reference(1.0f, v);

  /* Row taps at v = 0.25 (y = 0, iy = 0): -1, 0, 1, 2 with weights B, A, B, 0. Row 0 is hit by
   * tap 0 only (A) for periodic (1, 0, 1, 0) and black; by taps -1 and 0 (B, A) for clamp and
   * mirror (0, 0, 1, 1). */
  struct Sample {
    float u, v;
    float expected[4]; /* periodic, clamp, black, mirror */
    const char *label;
  };
  const Sample samples[] = {
      /* Centre of texel (0, 0): column taps -1, 0, 1, 2. periodic (3, 0, 1, 2) and black hit
       * column 0 with A; clamp and mirror (0, 0, 1, 2) with B and A. */
      {0.125f, 0.25f, {A * A, B * (B + A) + A * (B + A), A * A, B * (B + A) + A * (B + A)}, "P1"},
      /* Centre of texel (-2, 0): x = -2 is a negative integer, so frac() gives ix = -3 and
       * t = 1 (kernel/device/cpu/image.h:30-35): column taps -4, -3, -2, -1 with the weights
       * v[0..3] of t = 1. periodic wraps them to (0, 1, 2, 3): column 0 with v[0]. clamp (0, 0,
       * 0, 0): all four. black: ix < -2, so zero (kernel/device/cpu/image.h:252-254). mirror
       * (3, 2, 1, 0): column 0 with v[3]. */
      {-0.375f,
       0.25f,
       {A * v[0],
        B * (((v[0] + v[1]) + v[2]) + v[3]) + A * (((v[0] + v[1]) + v[2]) + v[3]),
        0.0f,
        B * v[3] + A * v[3]},
       "P2"},
      /* Centre of texel (3, 1): column taps 2, 3, 4, 5 and row taps 0, 1, 2, 3. periodic wraps
       * them to (2, 3, 0, 1) and (0, 1, 0, 1): column 0 with B, row 0 by the row taps 0 and 2
       * with B each. clamp (2, 3, 3, 3), black (2, 3, out, out) and mirror (2, 3, 3, 2) never
       * reach column 0. */
      {0.875f, 0.75f, {B * B + B * B, 0.0f, 0.0f, 0.0f}, "P3"},
      /* x = 0.5: ix = 0, tx = 0.5, column weights w[0..3]; rows as P1. periodic and black hit
       * column 0 with w[1]; clamp and mirror (0, 0, 1, 2) with w[0] and w[1]. */
      {0.25f,
       0.25f,
       {A * w[1],
        B * (w[0] + w[1]) + A * (w[0] + w[1]),
        A * w[1],
        B * (w[0] + w[1]) + A * (w[0] + w[1])},
       "P4"},
  };

  PainterlySvmTestProgram program = new_program();
  int lookups = 0;
  for (const Sample &sample : samples) {
    for (int e = 0; e < 4; e++) {
      const float e_value = sample.expected[e];
      add_sample(program,
                 ids[e],
                 sample.u,
                 sample.v,
                 make_float4(e_value, e_value, e_value, e_value),
                 std::string(sample.label) + " " + extension_names[e]);
      lookups++;
    }
  }
  add_sample(program,
             smart_id,
             0.125f,
             0.25f,
             make_float4(A * A, A * A, A * A, A * A),
             "P1 smart periodic");
  lookups++;
  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 2 * lookups);
}

/* What ImageMetaData::finalize() decides from the colour space and the source type
 * (util/image_metadata.cpp:130-147), and how the kernel reads each storage type. */
TEST_CASE("cycles svm images: storage types and colour spaces")
{
  ImageManager manager;

  /* Bytes in scene linear: stored as bytes, read as b * (1 / 255). */
  const ImageHandle linear_bytes = manager.add_image(
      byte_image(
          2, 1, PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR, {{0, 51, 255, 255}, {7, 10, 128, 255}}),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND));
  /* Bytes with the sRGB transfer function: stored as bytes and flagged compressible as sRGB. */
  const ImageHandle srgb_bytes = manager.add_image(
      byte_image(2,
                 1,
                 PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR_SRGB,
                 {{0, 0, 0, 255}, {255, 255, 255, 255}}),
      params(INTERPOLATION_LINEAR, EXTENSION_EXTEND));
  /* A byte source in another colour space, converted by the caller: stored as half floats.
   * 1/3 rounds to 1365/4096 in half precision; 65520 is clamped to 65504, the largest finite
   * half (float_to_half_image, util/half.h:284-287). */
  PainterlyImagePixels converted_bytes = float_image(
      1, 1, {make_float4(1.0f / 3.0f, 65520.0f, 0.25f, 1.0f)});
  converted_bytes.source_type = IMAGE_DATA_TYPE_BYTE4;
  converted_bytes.colorspace = PAINTERLY_IMAGE_COLORSPACE_CONVERTED;
  const ImageHandle half_image = manager.add_image(
      converted_bytes, params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND));
  /* A float source in another colour space stays float. */
  PainterlyImagePixels converted_floats = converted_bytes;
  converted_floats.source_type = IMAGE_DATA_TYPE_FLOAT4;
  const ImageHandle float_converted = manager.add_image(
      converted_floats, params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND));
  /* Floats with the sRGB transfer function stay float and are flagged too. */
  PainterlyImagePixels srgb_floats = float_image(1, 1, {make_float4(0.5f, 0.5f, 0.5f, 1.0f)});
  srgb_floats.colorspace = PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR_SRGB;
  const ImageHandle srgb_float_image = manager.add_image(
      srgb_floats, params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND));

  CHECK(manager.metadata(linear_bytes).type == IMAGE_DATA_TYPE_BYTE4);
  CHECK_FALSE(manager.metadata(linear_bytes).is_compressible_as_srgb);
  CHECK(manager.metadata(srgb_bytes).type == IMAGE_DATA_TYPE_BYTE4);
  CHECK(manager.metadata(srgb_bytes).is_compressible_as_srgb);
  CHECK(manager.metadata(half_image).type == IMAGE_DATA_TYPE_HALF4);
  CHECK_FALSE(manager.metadata(half_image).is_compressible_as_srgb);
  CHECK(manager.metadata(float_converted).type == IMAGE_DATA_TYPE_FLOAT4);
  CHECK(manager.metadata(srgb_float_image).type == IMAGE_DATA_TYPE_FLOAT4);
  CHECK(manager.metadata(srgb_float_image).is_compressible_as_srgb);

  /* Halfway between the sRGB bytes 0 and 255, the kernel interpolates the encoded values and
   * then converts: color_srgb_to_linear_v4(0.5). Converting first and then interpolating would
   * give 0.5 * 0 + 0.5 * color_srgb_to_linear(1), a different value. */
  const float one_byte = 255.0f * (1.0f / 255.0f);
  const float4 srgb_halfway = color_srgb_to_linear_v4(
      make_float4(0.5f * one_byte, 0.5f * one_byte, 0.5f * one_byte, one_byte));
  CHECK(srgb_halfway.x != 0.5f * color_srgb_to_linear(one_byte));

  KernelGlobalsCPU globals;
  bind_images(globals, manager);
  PainterlySvmTestProgram program = new_program();
  add_sample(program,
             linear_bytes.kernel_id(),
             0.25f,
             0.5f,
             make_float4(0.0f, 51.0f * (1.0f / 255.0f), 255.0f * (1.0f / 255.0f), one_byte),
             "linear bytes texel 0");
  add_sample(
      program,
      linear_bytes.kernel_id(),
      0.75f,
      0.5f,
      make_float4(
          7.0f * (1.0f / 255.0f), 10.0f * (1.0f / 255.0f), 128.0f * (1.0f / 255.0f), one_byte),
      "linear bytes texel 1");
  /* u = 0.5: x = 0.5, so tx = 0.5 between texels 0 and 1; v = 0.5: y = 0, ty = 0. */
  add_sample(program,
             srgb_bytes.kernel_id(),
             0.5f,
             0.5f,
             srgb_halfway,
             "sRGB bytes",
             NODE_IMAGE_COMPRESS_AS_SRGB);
  add_sample(program,
             half_image.kernel_id(),
             0.5f,
             0.5f,
             make_float4(1365.0f / 4096.0f, 65504.0f, 0.25f, 1.0f),
             "converted bytes as half");
  add_sample(program,
             float_converted.kernel_id(),
             0.5f,
             0.5f,
             make_float4(1.0f / 3.0f, 65520.0f, 0.25f, 1.0f),
             "converted floats as float");
  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 2 * 5);
}

/* Alpha as ImageMetaData::finalize() decides it (util/image_metadata.cpp:155-170) and
 * conform_pixels_to_metadata_type() applies it (util/image_metadata.cpp:498-509, 554-562,
 * 580-599). Bytes associate with integer division: 200 * 128 / 255 = 100, 100 * 128 / 255 = 50,
 * 255 * 128 / 255 = 128 (util/image.h:89-92). */
TEST_CASE("cycles svm images: alpha association, ignored alpha and non-finite pixels")
{
  ImageManager manager;
  const vector<uchar4> bytes = {{200, 100, 255, 128}};
  const ImageHandle byte_auto = manager.add_image(
      byte_image(1, 1, PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR, bytes),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND, IMAGE_ALPHA_AUTO));
  const ImageHandle byte_data = manager.add_image(
      byte_image(1, 1, PAINTERLY_IMAGE_COLORSPACE_DATA, bytes),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND, IMAGE_ALPHA_AUTO));
  const ImageHandle byte_ignore = manager.add_image(
      byte_image(1, 1, PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR, bytes),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND, IMAGE_ALPHA_IGNORE));
  const ImageHandle byte_packed = manager.add_image(
      byte_image(1, 1, PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR, bytes),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND, IMAGE_ALPHA_CHANNEL_PACKED));
  const ImageHandle byte_associated = manager.add_image(
      byte_image(1, 1, PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR, bytes),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND, IMAGE_ALPHA_ASSOCIATED));

  const vector<float4> floats = {make_float4(0.5f, 0.25f, 1.0f, 0.5f)};
  const ImageHandle float_auto = manager.add_image(
      float_image(1, 1, floats),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND, IMAGE_ALPHA_AUTO));
  const ImageHandle float_unassociated = manager.add_image(
      float_image(1, 1, floats),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND, IMAGE_ALPHA_UNASSOCIATED));
  PainterlyImagePixels converted = float_image(1, 1, floats);
  converted.source_type = IMAGE_DATA_TYPE_BYTE4;
  converted.colorspace = PAINTERLY_IMAGE_COLORSPACE_CONVERTED;
  converted.is_unassociated_alpha = true;
  const ImageHandle half_auto = manager.add_image(
      converted, params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND, IMAGE_ALPHA_AUTO));

  const float inf = std::numeric_limits<float>::infinity();
  const ImageHandle non_finite = manager.add_image(
      float_image(2, 1, {make_float4(inf, 0.5f, 0.5f, 1.0f), make_float4(0.5f, 0.5f, 0.5f, 1.0f)}),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND));

  CHECK(manager.metadata(byte_auto).is_unassociated_alpha);
  CHECK_FALSE(manager.metadata(byte_data).is_unassociated_alpha);
  CHECK(manager.metadata(byte_ignore).ignore_alpha);
  CHECK_FALSE(manager.metadata(byte_ignore).is_unassociated_alpha);
  CHECK(manager.metadata(byte_packed).is_channel_packed);
  CHECK_FALSE(manager.metadata(byte_packed).is_unassociated_alpha);
  CHECK_FALSE(manager.metadata(byte_associated).is_unassociated_alpha);
  CHECK_FALSE(manager.metadata(float_auto).is_unassociated_alpha);
  CHECK(manager.metadata(float_unassociated).is_unassociated_alpha);
  CHECK(manager.metadata(half_auto).is_unassociated_alpha);

  const float f = 1.0f / 255.0f;
  const float4 as_given = make_float4(200.0f * f, 100.0f * f, 255.0f * f, 128.0f * f);

  KernelGlobalsCPU globals;
  bind_images(globals, manager);
  PainterlySvmTestProgram program = new_program();
  add_sample(program,
             byte_auto.kernel_id(),
             0.5f,
             0.5f,
             make_float4(100.0f * f, 50.0f * f, 128.0f * f, 128.0f * f),
             "bytes associated");
  add_sample(program, byte_data.kernel_id(), 0.5f, 0.5f, as_given, "data bytes");
  add_sample(program,
             byte_ignore.kernel_id(),
             0.5f,
             0.5f,
             make_float4(200.0f * f, 100.0f * f, 255.0f * f, 255.0f * f),
             "bytes alpha ignored");
  add_sample(program, byte_packed.kernel_id(), 0.5f, 0.5f, as_given, "bytes channel packed");
  add_sample(program, byte_associated.kernel_id(), 0.5f, 0.5f, as_given, "bytes associated given");
  add_sample(
      program, float_auto.kernel_id(), 0.5f, 0.5f, make_float4(0.5f, 0.25f, 1.0f, 0.5f), "floats");
  add_sample(program,
             float_unassociated.kernel_id(),
             0.5f,
             0.5f,
             make_float4(0.25f, 0.125f, 0.5f, 0.5f),
             "floats associated");
  add_sample(program,
             half_auto.kernel_id(),
             0.5f,
             0.5f,
             make_float4(0.25f, 0.125f, 0.5f, 0.5f),
             "halfs associated");
  add_sample(program, non_finite.kernel_id(), 0.25f, 0.5f, zero_float4(), "non-finite texel");
  add_sample(program,
             non_finite.kernel_id(),
             0.75f,
             0.5f,
             make_float4(0.5f, 0.5f, 0.5f, 1.0f),
             "finite texel");
  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 2 * 10);
}

/* svm_image_texture() (kernel/svm/image.h:22-38): NODE_IMAGE_ALPHA_UNASSOCIATE divides the colour
 * by an alpha other than 0 and 1; an empty handle samples no array and gives IMAGE_MISSING_RGBA;
 * so does a missing image, after reading its KernelImageTexture
 * (kernel/device/cpu/image.h:333-361). */
TEST_CASE("cycles svm images: unassociate flag and missing images")
{
  ImageManager manager;
  const ImageHandle empty_image = manager.add_image(
      PainterlyImagePixels(), params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND));
  PainterlyImagePixels wrong_size = float_image(2, 2, {one_float4(), one_float4(), one_float4()});
  const ImageHandle invalid_image = manager.add_image(
      wrong_size, params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND));
  const ImageHandle half_alpha = manager.add_image(
      float_image(1, 1, {make_float4(0.25f, 0.125f, 0.5f, 0.5f)}),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND));
  const ImageHandle zero_alpha = manager.add_image(
      float_image(1, 1, {make_float4(0.25f, 0.125f, 0.5f, 0.0f)}),
      params(INTERPOLATION_CLOSEST, EXTENSION_EXTEND));

  CHECK(manager.metadata(empty_image).type == IMAGE_DATA_NUM_TYPES);
  CHECK(manager.metadata(invalid_image).type == IMAGE_DATA_NUM_TYPES);
  CHECK(manager.get_image_textures()[empty_image.kernel_id()].image_info_id == KERNEL_IMAGE_NONE);
  CHECK(manager.get_image_textures()[invalid_image.kernel_id()].image_info_id ==
        KERNEL_IMAGE_NONE);
  CHECK(manager.get_image_textures()[half_alpha.kernel_id()].image_info_id == 0);
  CHECK(manager.get_image_info().size() == 2);

  const float4 magenta = make_float4(1.0f, 0.0f, 1.0f, 1.0f);
  KernelGlobalsCPU globals;
  bind_images(globals, manager);
  PainterlySvmTestProgram program = new_program();
  add_sample(program,
             half_alpha.kernel_id(),
             0.5f,
             0.5f,
             make_float4(0.5f, 0.25f, 1.0f, 0.5f),
             "unassociated",
             NODE_IMAGE_ALPHA_UNASSOCIATE);
  add_sample(program,
             zero_alpha.kernel_id(),
             0.5f,
             0.5f,
             make_float4(0.25f, 0.125f, 0.5f, 0.0f),
             "alpha 0 kept",
             NODE_IMAGE_ALPHA_UNASSOCIATE);
  add_sample(program, empty_image.kernel_id(), 0.5f, 0.5f, magenta, "empty image");
  add_sample(program, invalid_image.kernel_id(), 0.5f, 0.5f, magenta, "invalid image");
  add_sample(program, ImageHandle().kernel_id(), 0.5f, 0.5f, magenta, "empty handle");
  ShaderData sd = painterly_svm_test_shader_data(0);
  /* Two lookups of 2 fetches, two missing images of 1 fetch each, and the empty handle with
   * none. */
  run_and_check(globals, program, sd, 2 * 2 + 1 + 1 + 0);
}

/* Box projection (kernel/svm/image.h:78-175), environment projections (:177-205) and the
 * *_DERIVATIVE cases, which sample untiled images at the same point as the plain cases. */
TEST_CASE("cycles svm images: box and environment projections and the derivative cases")
{
  ImageManager manager;
  const int id = manager.add_image(value_image(), params(INTERPOLATION_CLOSEST, EXTENSION_REPEAT))
                     .kernel_id();
  KernelGlobalsCPU globals;
  bind_images(globals, manager);

  PainterlySvmTestProgram program = new_program();

  /* NODE_TEX_IMAGE_DERIVATIVE at (0.375, 0.25): texel (1, 0), as the closest test. */
  program.add_node(
      NODE_VALUE_V_DERIVATIVE,
      SVMNodeValueV{.out_offset = co_slot, .value = make_float3(0.375f, 0.25f, 0.0f)});
  program.add_node(NODE_TEX_IMAGE_DERIVATIVE,
                   SVMNodeTexImage{.id = id,
                                   .projection = NODE_IMAGE_PROJ_FLAT,
                                   .flags = 0,
                                   .co = co_slot,
                                   .out_offset = color_slot,
                                   .alpha_offset = alpha_slot});
  check_sample(program, texel(1, 0), "image derivative");

  /* Box with N = (0, 0, 1) and blend 0: only the z face, weight 1, at uv = (1 - co.y, co.x)
   * (kernel/svm/image.h:118-120, 164-167). co = (0.25, 0.375, 0) gives uv = (0.625, 0.25),
   * x = 2.5, y = 0.5: texel (2, 0). */
  for (const ShaderNodeType type : {NODE_TEX_IMAGE_BOX, NODE_TEX_IMAGE_BOX_DERIVATIVE}) {
    program.add_node(
        type == NODE_TEX_IMAGE_BOX ? NODE_VALUE_V : NODE_VALUE_V_DERIVATIVE,
        SVMNodeValueV{.out_offset = co_slot, .value = make_float3(0.25f, 0.375f, 0.0f)});
    program.add_node(type,
                     SVMNodeTexImageBox{.id = id,
                                        .blend = 0.0f,
                                        .flags = 0,
                                        .co = co_slot,
                                        .out_offset = color_slot,
                                        .alpha_offset = alpha_slot});
    check_sample(program, texel(2, 0), type == NODE_TEX_IMAGE_BOX ? "box" : "box derivative");
  }

  /* Equirectangular, direction (1, 1, -sqrt 2): u = (atan2(1, 1) - pi) / -2pi = 0.375 and
   * v = (acos(-1/sqrt 2) - pi) / -pi = 0.25 (kernel/camera/projection.h:19-29, 52-55), so
   * x = 1.5 and y = 0.5, texel (1, 0). Rounding in the C library's atan2f() and acosf() moves x
   * and y by a few float32 ulps, far less than the half texel between them and a texel edge, so
   * the texel is certain and its value is compared exactly. */
  program.add_node(
      NODE_VALUE_V,
      SVMNodeValueV{.out_offset = co_slot, .value = make_float3(1.0f, 1.0f, -1.41421356f)});
  program.add_node(NODE_TEX_ENVIRONMENT,
                   SVMNodeTexEnvironment{.id = id,
                                         .projection = NODE_ENVIRONMENT_EQUIRECTANGULAR,
                                         .flags = 0,
                                         .co = co_slot,
                                         .out_offset = color_slot,
                                         .alpha_offset = alpha_slot});
  check_sample(program, texel(1, 0), "equirectangular");

  /* Mirror ball, direction (0, -2, 0): normalised (0, -1, 0); x and z stay 0, so
   * uv = (0.5 * (0 + 1), 0.5 * (0 + 1)) = (0.5, 0.5) exactly (kernel/camera/projection.h:238-265),
   * x = 2 and y = 1: texel (2, 1). */
  for (const ShaderNodeType type : {NODE_TEX_ENVIRONMENT, NODE_TEX_ENVIRONMENT_DERIVATIVE}) {
    program.add_node(
        type == NODE_TEX_ENVIRONMENT ? NODE_VALUE_V : NODE_VALUE_V_DERIVATIVE,
        SVMNodeValueV{.out_offset = co_slot, .value = make_float3(0.0f, -2.0f, 0.0f)});
    program.add_node(type,
                     SVMNodeTexEnvironment{.id = id,
                                           .projection = NODE_ENVIRONMENT_MIRROR_BALL,
                                           .flags = 0,
                                           .co = co_slot,
                                           .out_offset = color_slot,
                                           .alpha_offset = alpha_slot});
    check_sample(program,
                 texel(2, 1),
                 type == NODE_TEX_ENVIRONMENT ? "mirror ball" : "mirror ball derivative");
  }

  /* Box: no object, so object_inverse_normal_transform() reads no array
   * (kernel/geom/object.h:180-197). */
  ShaderData sd = painterly_svm_test_shader_data(0);
  sd.N = make_float3(0.0f, 0.0f, 1.0f);
  sd.object = OBJECT_NONE;
  run_and_check(globals, program, sd, 2 * 6);
}

/* The kernel arrays that ImageManager::add_image() fills (scene/image.cpp:482-489,
 * scene/image_cache.cpp:125-149, device/memory.cpp:214-306), and the handle. */
TEST_CASE("cycles svm images: image manager arrays and handles")
{
  const ImageParams defaults;
  CHECK(defaults.interpolation == INTERPOLATION_LINEAR);
  CHECK(defaults.extension == EXTENSION_CLIP);
  CHECK(defaults.alpha_type == IMAGE_ALPHA_AUTO);
  CHECK(defaults == ImageParams());
  CHECK_FALSE(defaults == params(INTERPOLATION_CUBIC, EXTENSION_CLIP));

  const ImageHandle none;
  CHECK(none.empty());
  CHECK(none.kernel_id() == KERNEL_IMAGE_NONE);
  CHECK(none.get_manager() == nullptr);

  ImageManager manager;
  CHECK_FALSE(manager.get_use_texture_cache());
  CHECK_FALSE(manager.get_auto_texture_cache());
  CHECK(manager.metadata(none).type == IMAGE_DATA_NUM_TYPES);

  const PainterlyImagePixels pixels = value_image();
  const ImageHandle first = manager.add_image(pixels,
                                              params(INTERPOLATION_CUBIC, EXTENSION_MIRROR));
  const ImageHandle second = manager.add_image(pixels,
                                               params(INTERPOLATION_CUBIC, EXTENSION_MIRROR));
  CHECK_FALSE(first.empty());
  CHECK(first.kernel_id() == 0);
  CHECK(second.kernel_id() == 1);
  CHECK(first.get_manager() == &manager);
  CHECK(first == ImageHandle(first));
  CHECK_FALSE(first == second);

  REQUIRE(manager.get_image_textures().size() == 2);
  REQUIRE(manager.get_image_info().size() == 2);
  const KernelImageTexture &tex = manager.get_image_textures()[1];
  CHECK(tex.image_info_id == 1);
  CHECK(tex.tile_descriptor_offset == UINT_MAX);
  CHECK(tex.tile_descriptor_offset == KERNEL_TILE_LOAD_NONE);
  CHECK(tex.width == 4);
  CHECK(tex.height == 2);
  CHECK(tex.interpolation == INTERPOLATION_CUBIC);
  CHECK(tex.extension == EXTENSION_MIRROR);
  CHECK(tex.use_transform_3d == 0);

  const KernelImageInfo &info = manager.get_image_info()[1];
  CHECK(info.data_type == IMAGE_DATA_TYPE_FLOAT4);
  CHECK(info.interpolation == INTERPOLATION_CUBIC);
  CHECK(info.extension == EXTENSION_MIRROR);
  CHECK(info.width == 4);
  CHECK(info.height == 2);
  CHECK(info.inv_width == 0.25f);
  CHECK(info.inv_height == 0.5f);
  REQUIRE(info.data != 0);
  CHECK(info.data != manager.get_image_info()[0].data);
  const float4 *stored = reinterpret_cast<const float4 *>(info.data);
  for (int i = 0; i < 8; i++) {
    CAPTURE(i);
    CHECK(stored[i].x == pixels.floats[i].x);
    CHECK(stored[i].y == pixels.floats[i].y);
    CHECK(stored[i].z == pixels.floats[i].z);
    CHECK(stored[i].w == pixels.floats[i].w);
  }

  const PainterlyImageMetaData metadata = manager.metadata(second);
  CHECK(metadata.type == IMAGE_DATA_TYPE_FLOAT4);
  CHECK(metadata.width == 4);
  CHECK(metadata.height == 2);
  CHECK_FALSE(metadata.is_compressible_as_srgb);
  CHECK_FALSE(metadata.is_unassociated_alpha);
  CHECK_FALSE(metadata.ignore_alpha);
  CHECK_FALSE(metadata.is_channel_packed);
}

CCL_NAMESPACE_END
