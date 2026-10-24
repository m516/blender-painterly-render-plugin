/* Shim: replaces Cycles scene/image.h without OIIO, OCIO, devices or the texture cache */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 * SPDX-FileCopyrightText: 2011-2026 Blender Authors
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: ImageParams without animated, colorspace and frame;
 * ImageHandle for one untiled image; ImageManager reduced to add_image() of pixels given in
 * memory; and the painterly types PainterlyImageColorSpace, PainterlyImagePixels and
 * PainterlyImageMetaData. */

#pragma once

#define PAINTERLY_SHIM_SCENE_IMAGE_H 1

#include "util/half.h"
#include "util/types_float4.h"
#include "util/types_image.h"
#include "util/types_uchar4.h"
#include "util/unique_ptr.h"
#include "util/vector.h"

CCL_NAMESPACE_BEGIN

class ImageManager;

/* Upstream's ImageParams (scene/image.h:38-55) reduced to the members that the in-memory path
 * reads, with upstream's defaults. Upstream also has animated, colorspace and frame: painterly
 * gets one frame of pixels from Blender, and the colour space comes with the pixels
 * (PainterlyImagePixels). Upstream's operator== compares every member (scene/image.h:49-54);
 * the defaulted one does the same, also for members that a later card adds. */
class ImageParams {
 public:
  InterpolationType interpolation = INTERPOLATION_LINEAR;
  ExtensionType extension = EXTENSION_CLIP;
  ImageAlphaType alpha_type = IMAGE_ALPHA_AUTO;

  bool operator==(const ImageParams &other) const = default;
};

/* Painterly: how an image's colour space relates to scene linear. Upstream decides it with OCIO
 * in ColorSpaceManager::detect_known_colorspace() (util/colorspace.cpp:281-383). Painterly has
 * no OCIO, so the caller decides it (card T6.8; experiment X-colour). It selects what
 * ImageMetaData::finalize() selects (util/image_metadata.cpp:124-170). */
enum PainterlyImageColorSpace {
  /* u_colorspace_scene_linear: stored as given. */
  PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR = 0,
  /* u_colorspace_scene_linear_srgb: scene linear primaries with the sRGB transfer function.
   * Stored as given; the kernel converts to linear after interpolation
   * (is_compressible_as_srgb, util/image_metadata.cpp:133-137; NODE_IMAGE_COMPRESS_AS_SRGB,
   * kernel/svm/image.h:33-35). */
  PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR_SRGB = 1,
  /* u_colorspace_data: non-colour data, stored as given; its alpha is never associated
   * (util/image_metadata.cpp:159-163). */
  PAINTERLY_IMAGE_COLORSPACE_DATA = 2,
  /* Any other colour space. Upstream converts it to scene linear with OCIO when it loads the
   * pixels, and stores a byte source as half floats (util/image_metadata.cpp:138-147, 565-578).
   * Painterly has no OCIO: the caller converts and gives the result as `floats`, and add_image()
   * stores and conforms it as for the other classes. Below, c is a pixel's colour, a its alpha
   * and conv() the conversion to scene linear. For a byte source, c and a are the half floats
   * float_to_half_image(b / 255) that upstream converts (blender/image.cpp:146-154).
   * - Upstream converts each RGBA pixel as conv(c * (1 / a)) * a, in float32 in this order, and
   *   as conv(c) when a <= 0, a == 1, or the alpha type is IMAGE_ALPHA_IGNORE or
   *   IMAGE_ALPHA_CHANNEL_PACKED (util/colorspace.cpp:498-503, 524-528;
   *   util/image_metadata.cpp:565-578). Unassociated alpha it associates before that
   *   (util/image_metadata.cpp:498-509).
   * - If add_image() does not associate the alpha (IMAGE_ALPHA_ASSOCIATED; IMAGE_ALPHA_AUTO with
   *   an associated source, such as every Blender float buffer; IMAGE_ALPHA_IGNORE;
   *   IMAGE_ALPHA_CHANNEL_PACKED), the caller passes upstream's converted values above. Painterly
   *   then stores what upstream stores.
   * - If add_image() associates the alpha (IMAGE_ALPHA_UNASSOCIATED, or IMAGE_ALPHA_AUTO with an
   *   unassociated source), the caller passes conv(c) of the straight values and add_image()
   *   multiplies by a afterwards. This agrees with upstream when a == 1, and when a == 0 if
   *   conv(0) == 0; otherwise only up to rounding (card T6.8, Decision 4; experiment X-colour). */
  PAINTERLY_IMAGE_COLORSPACE_CONVERTED = 3,
};

/* Painterly: one image as Blender holds it in memory, the input that upstream's
 * BlenderImageLoader reads (blender/image.cpp:46-94). Painterly treats every image as a Blender
 * builtin image: it has no file loader. */
struct PainterlyImagePixels {
  /* Dimensions in pixels. If either is 0 the image is missing, as upstream treats an empty image
   * (scene/image_cache.cpp:200-216): the kernel returns IMAGE_MISSING_RGBA. */
  int width = 0;
  int height = 0;
  /* What Blender's buffer holds: IMAGE_DATA_TYPE_BYTE4 (a byte buffer) or
   * IMAGE_DATA_TYPE_FLOAT4 (a float buffer), as BlenderImageLoader::load_metadata() reports it
   * (blender/image.cpp:72-91). */
  ImageDataType source_type = IMAGE_DATA_TYPE_FLOAT4;
  PainterlyImageColorSpace colorspace = PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR;
  /* Whether the source's alpha is unassociated. BlenderImageLoader sets it for byte buffers and
   * clears it for float buffers (blender/image.cpp:62). */
  bool is_unassociated_alpha = false;
  /* width * height pixels, row by row, the first row at v = 0 (y = v * height,
   * kernel/device/cpu/image.h:365). A byte source is in `bytes`. A float source is in `floats`,
   * and so is a source of any type in PAINTERLY_IMAGE_COLORSPACE_CONVERTED, converted to scene
   * linear by the caller as that class's comment says. The other vector is empty. */
  vector<uchar4> bytes;
  vector<float4> floats;
};

/* Painterly: the part of upstream's ImageMetaData (util/image_metadata.h:24-95) that
 * ImageMetaData::finalize() decides (util/image_metadata.cpp:124-170). Upstream's class needs
 * OIIO. */
struct PainterlyImageMetaData {
  /* The storage type: IMAGE_DATA_TYPE_BYTE4, IMAGE_DATA_TYPE_HALF4 or IMAGE_DATA_TYPE_FLOAT4.
   * IMAGE_DATA_NUM_TYPES for a missing image. */
  ImageDataType type = IMAGE_DATA_NUM_TYPES;
  int width = 0;
  int height = 0;
  bool is_compressible_as_srgb = false;
  bool is_unassociated_alpha = false;
  bool ignore_alpha = false;
  bool is_channel_packed = false;
};

/* Upstream's ImageHandle (scene/image.h:63-96) for a single image in the in-memory path:
 * no reference counting, no UDIM tiles and no volume images. The image lives as long as its
 * ImageManager. scene/shader_nodes.h holds an ImageHandle by value (:102, :196) and compares two
 * of them (:91). */
class ImageHandle {
 public:
  /* scene/image.cpp:99-102. */
  bool empty() const
  {
    return manager == nullptr;
  }

  /* The image's index into the kernel array image_textures, KERNEL_IMAGE_NONE for an empty
   * handle (scene/image.cpp:145-154). */
  int kernel_id() const
  {
    return image_texture_id;
  }

  /* scene/image.cpp:185-188. */
  ImageManager *get_manager() const
  {
    return manager;
  }

  /* Upstream compares the manager and the image (scene/image.cpp:190-193). */
  bool operator==(const ImageHandle &other) const = default;

 protected:
  ImageManager *manager = nullptr;
  int image_texture_id = KERNEL_IMAGE_NONE;

  friend class ImageManager;
};

/* Upstream's ImageManager (scene/image.h:149-238) for images given in memory, loaded on the CPU
 * without the texture cache. add_image() loads the pixels at once into host memory, conformed as
 * upstream conforms them (util/image_metadata.cpp:484-611), and fills the kernel arrays
 * image_textures and image_info (kernel/data_arrays.h:93, 97) as upstream's device update does
 * (scene/image.cpp:467-523; scene/image_cache.cpp:125-149, 192-274; device/memory.cpp:214-306).
 * Every image is untiled: KernelImageTexture::tile_descriptor_offset keeps its default
 * KERNEL_TILE_LOAD_NONE, which is UINT_MAX (util/types_image.h:120, 149), so the kernel samples
 * image_info directly (kernel/device/cpu/image.h:341-366). Not thread safe: painterly adds images
 * from one thread, before rendering. */
class ImageManager {
 public:
  ImageManager();
  ~ImageManager();

  ImageManager(const ImageManager &) = delete;
  ImageManager &operator=(const ImageManager &) = delete;

  /* Upstream's add_image() of a builtin image (scene/image.cpp:324-330, 350-389), with the pixels
   * in place of the loader. Every call adds a new image; upstream reuses an image whose loader and
   * params are equal (scene/image.cpp:356-363), which painterly's caller does by keeping its
   * handles. Invalid pixels (see PainterlyImagePixels) give a missing image and an error in the
   * log, as a failed load does upstream (scene/image_cache.cpp:237-244). */
  ImageHandle add_image(const PainterlyImagePixels &pixels, const ImageParams &params);

  /* scene/image.h:184-185: painterly never uses the texture cache. */
  bool get_use_texture_cache() const
  {
    return false;
  }
  bool get_auto_texture_cache() const
  {
    return false;
  }

  /* Painterly: the metadata of `handle`'s image; a default PainterlyImageMetaData for an empty
   * handle. */
  PainterlyImageMetaData metadata(const ImageHandle &handle) const;

  /* Painterly: the kernel arrays image_textures and image_info, indexed by
   * ImageHandle::kernel_id() and KernelImageTexture::image_info_id. add_image() may move the
   * arrays, so bind them to KernelGlobalsCPU after the last add_image(). KernelImageInfo::data
   * points into this manager's pixel storage and stays valid until the manager is destroyed. */
  const vector<KernelImageTexture> &get_image_textures() const
  {
    return image_textures;
  }
  const vector<KernelImageInfo> &get_image_info() const
  {
    return image_info;
  }

 private:
  /* The pixels of one image in its storage type; only the vector of that type is non-empty. */
  struct Storage {
    PainterlyImageMetaData metadata;
    vector<uchar4> bytes;
    vector<half4> halfs;
    vector<float4> floats;
  };

  vector<unique_ptr<Storage>> images;
  vector<KernelImageTexture> image_textures;
  vector<KernelImageInfo> image_info;
};

CCL_NAMESPACE_END
