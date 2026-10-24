/* Shim: replaces Cycles scene/image.cpp without OIIO, OCIO, devices or the texture cache */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 * SPDX-FileCopyrightText: 2011-2025 Blender Foundation
 * SPDX-FileCopyrightText: 2011-2026 Blender Authors
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: ImageManager::add_image() of pixels given in memory, with
 * the pixel conforming of util/image_metadata.cpp and util/image.h and the kernel array fill of
 * scene/image.cpp, scene/image_cache.cpp and device/memory.cpp, without OIIO, OCIO, devices or
 * the texture cache. */

#include "scene/image.h"

#include <cmath>

#include "util/log.h"

CCL_NAMESPACE_BEGIN

namespace {

/* util_image_cast_from_float(1.0f) for each storage type (util/image.h:53-80): the alpha that
 * IMAGE_ALPHA_IGNORE writes (util/image_metadata.cpp:512, 554-562). */
uchar4 with_opaque_alpha(uchar4 pixel)
{
  pixel.w = 255;
  return pixel;
}

half4 with_opaque_alpha(half4 pixel)
{
  pixel.w = float_to_half_image(1.0f);
  return pixel;
}

float4 with_opaque_alpha(float4 pixel)
{
  pixel.w = 1.0f;
  return pixel;
}

/* util_image_multiply_native() (util/image.h:83-100), applied to the colour channels as
 * conform_pixels_to_metadata_type() associates alpha (util/image_metadata.cpp:498-509). */
uchar4 associate_alpha(uchar4 pixel)
{
  const uchar alpha = pixel.w;
  pixel.x = uchar(((uint32_t)pixel.x * (uint32_t)alpha) / 255);
  pixel.y = uchar(((uint32_t)pixel.y * (uint32_t)alpha) / 255);
  pixel.z = uchar(((uint32_t)pixel.z * (uint32_t)alpha) / 255);
  return pixel;
}

half4 associate_alpha(half4 pixel)
{
  const half alpha = pixel.w;
  pixel.x = float_to_half_image(half_to_float_image(pixel.x) * half_to_float_image(alpha));
  pixel.y = float_to_half_image(half_to_float_image(pixel.y) * half_to_float_image(alpha));
  pixel.z = float_to_half_image(half_to_float_image(pixel.z) * half_to_float_image(alpha));
  return pixel;
}

float4 associate_alpha(float4 pixel)
{
  const float alpha = pixel.w;
  pixel.x = pixel.x * alpha;
  pixel.y = pixel.y * alpha;
  pixel.z = pixel.z * alpha;
  return pixel;
}

/* util_image_is_finite() (util/image.h:103-120) of all four channels: an RGBA pixel with any
 * non-finite channel becomes zero (util/image_metadata.cpp:580-599). Bytes are always finite. */
uchar4 zero_if_not_finite(const uchar4 pixel)
{
  return pixel;
}

half4 zero_if_not_finite(half4 pixel)
{
  if (!half_is_finite(pixel.x) || !half_is_finite(pixel.y) || !half_is_finite(pixel.z) ||
      !half_is_finite(pixel.w))
  {
    const half zero = float_to_half_image(0.0f);
    pixel = {zero, zero, zero, zero};
  }
  return pixel;
}

float4 zero_if_not_finite(float4 pixel)
{
  if (!std::isfinite(pixel.x) || !std::isfinite(pixel.y) || !std::isfinite(pixel.z) ||
      !std::isfinite(pixel.w))
  {
    pixel = zero_float4();
  }
  return pixel;
}

/* conform_pixels_to_metadata_type() (util/image_metadata.cpp:484-611) for RGBA pixels whose
 * colour space needs no conversion here: associate alpha, then ignore alpha, then zero the
 * non-finite pixels, in upstream's order. */
template<typename StorageType>
void conform_pixels(const PainterlyImageMetaData &metadata, vector<StorageType> &pixels)
{
  for (StorageType &pixel : pixels) {
    if (metadata.is_unassociated_alpha) {
      pixel = associate_alpha(pixel);
    }
    if (metadata.ignore_alpha) {
      pixel = with_opaque_alpha(pixel);
    }
    pixel = zero_if_not_finite(pixel);
  }
}

/* The reason why `pixels` cannot be loaded, or nullptr if they can. */
const char *invalid_pixels_reason(const PainterlyImagePixels &pixels)
{
  if (pixels.width < 0 || pixels.height < 0) {
    return "negative size";
  }
  if (pixels.width == 0 || pixels.height == 0) {
    return "empty image";
  }
  const size_t num_pixels = size_t(pixels.width) * size_t(pixels.height);
  const bool use_bytes = pixels.source_type == IMAGE_DATA_TYPE_BYTE4 &&
                         pixels.colorspace != PAINTERLY_IMAGE_COLORSPACE_CONVERTED;
  if (pixels.source_type != IMAGE_DATA_TYPE_BYTE4 && pixels.source_type != IMAGE_DATA_TYPE_FLOAT4)
  {
    return "source_type is neither IMAGE_DATA_TYPE_BYTE4 nor IMAGE_DATA_TYPE_FLOAT4";
  }
  if (use_bytes && (pixels.bytes.size() != num_pixels || !pixels.floats.empty())) {
    return "a byte image needs width * height bytes and no floats";
  }
  if (!use_bytes && (pixels.floats.size() != num_pixels || !pixels.bytes.empty())) {
    return "a float or converted image needs width * height floats and no bytes";
  }
  return nullptr;
}

}  // namespace

ImageManager::ImageManager() = default;

ImageManager::~ImageManager() = default;

ImageHandle ImageManager::add_image(const PainterlyImagePixels &pixels, const ImageParams &params)
{
  unique_ptr<Storage> storage = make_unique<Storage>();
  PainterlyImageMetaData &metadata = storage->metadata;

  /* scene/image.cpp:482-489: the texture's size, interpolation and extension. The metadata's
   * defaults give use_transform_3d = false, transform_3d = identity and a zero average colour
   * (util/image_metadata.h:38, 47-48). */
  KernelImageTexture tex;
  tex.interpolation = params.interpolation;
  tex.extension = params.extension;
  tex.use_transform_3d = false;
  tex.transform_3d = transform_identity();
  tex.average_color = zero_float4();

  const char *invalid = invalid_pixels_reason(pixels);
  if (invalid) {
    if (pixels.width != 0 && pixels.height != 0) {
      LOG_ERROR << "Image texture " << images.size() << " not loaded: " << invalid << "\n";
    }
    /* A missing image: image_info_id stays KERNEL_IMAGE_NONE (scene/image_cache.cpp:200-216,
     * 237-244), and the kernel returns IMAGE_MISSING_RGBA (kernel/device/cpu/image.h:359-361). */
  }
  else {
    /* ImageMetaData::finalize() (util/image_metadata.cpp:124-170). */
    metadata.width = pixels.width;
    metadata.height = pixels.height;
    metadata.type = pixels.source_type;
    if (pixels.colorspace == PAINTERLY_IMAGE_COLORSPACE_SCENE_LINEAR_SRGB) {
      metadata.is_compressible_as_srgb = true;
    }
    else if (pixels.colorspace == PAINTERLY_IMAGE_COLORSPACE_CONVERTED &&
             pixels.source_type == IMAGE_DATA_TYPE_BYTE4)
    {
      metadata.type = IMAGE_DATA_TYPE_HALF4;
    }
    metadata.ignore_alpha = params.alpha_type == IMAGE_ALPHA_IGNORE;
    metadata.is_channel_packed = params.alpha_type == IMAGE_ALPHA_CHANNEL_PACKED;
    if (pixels.colorspace == PAINTERLY_IMAGE_COLORSPACE_DATA ||
        params.alpha_type == IMAGE_ALPHA_ASSOCIATED || params.alpha_type == IMAGE_ALPHA_IGNORE ||
        params.alpha_type == IMAGE_ALPHA_CHANNEL_PACKED)
    {
      metadata.is_unassociated_alpha = false;
    }
    else if (params.alpha_type == IMAGE_ALPHA_UNASSOCIATED) {
      metadata.is_unassociated_alpha = true;
    }
    else {
      metadata.is_unassociated_alpha = pixels.is_unassociated_alpha;
    }

    /* The pixels in their storage type, conformed. A converted byte source becomes half floats
     * with float_to_half_image(), as BlenderImageLoader's load_half_pixels() stores them
     * (blender/image.cpp:146-154). */
    const void *data = nullptr;
    switch (metadata.type) {
      case IMAGE_DATA_TYPE_BYTE4:
        storage->bytes = pixels.bytes;
        conform_pixels(metadata, storage->bytes);
        data = storage->bytes.data();
        break;
      case IMAGE_DATA_TYPE_HALF4:
        storage->halfs.reserve(pixels.floats.size());
        for (const float4 &pixel : pixels.floats) {
          storage->halfs.push_back({float_to_half_image(pixel.x),
                                    float_to_half_image(pixel.y),
                                    float_to_half_image(pixel.z),
                                    float_to_half_image(pixel.w)});
        }
        conform_pixels(metadata, storage->halfs);
        data = storage->halfs.data();
        break;
      default:
        storage->floats = pixels.floats;
        conform_pixels(metadata, storage->floats);
        data = storage->floats.data();
        break;
    }

    /* scene/image.cpp:483-484: the texture's size. */
    tex.width = metadata.width;
    tex.height = metadata.height;

    /* ImageCache::alloc_full() (scene/image_cache.cpp:125-149), with what the device_image
     * constructor and alloc() write into KernelImageInfo (device/memory.cpp:214-268, 290-306),
     * and the host pointer that the CPU device stores in it (device/cpu/device_impl.cpp:258-259).
     */
    KernelImageInfo info;
    info.data = (uint64_t)data;
    info.data_type = metadata.type;
    info.interpolation = params.interpolation;
    info.extension = params.extension;
    info.width = metadata.width;
    info.height = metadata.height;
    info.inv_width = 1.0f / (float)metadata.width;
    info.inv_height = 1.0f / (float)metadata.height;
    tex.image_info_id = uint(image_info.size());
    image_info.push_back(info);
  }

  ImageHandle handle;
  handle.manager = this;
  handle.image_texture_id = int(image_textures.size());
  image_textures.push_back(tex);
  images.push_back(std::move(storage));
  return handle;
}

PainterlyImageMetaData ImageManager::metadata(const ImageHandle &handle) const
{
  if (handle.manager != this || handle.image_texture_id == KERNEL_IMAGE_NONE) {
    return PainterlyImageMetaData();
  }
  return images[handle.image_texture_id]->metadata;
}

CCL_NAMESPACE_END
